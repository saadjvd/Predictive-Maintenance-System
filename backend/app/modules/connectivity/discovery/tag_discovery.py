import asyncio
import logging
from typing import Optional, List, Set, Tuple
import asyncua
from asyncua import Node, ua

from app.modules.connectivity.models import (
    OPCUAError,
    ReadOnlyError,
)
from app.modules.connectivity.opcua_client import SecureOPCUAClient
from app.modules.connectivity.discovery.node_metadata import (
    DiscoveredTag,
    extract_node_metadata,
)

logger = logging.getLogger(__name__)


class TagDiscoveryService:
    """Automatic OPC UA address space tag discovery service.
    
    Adheres strictly to Phase 4, Step 5 specifications:
    - Bounded browse depth & maximum node limits
    - Cycle protection against circular references
    - Recursive and lazy address space browsing
    - Universal normalized metadata extraction
    - Safe search and readability validation
    - Strictly read-only
    """

    def __init__(
        self,
        default_timeout_sec: float = 4.0,
        max_nodes_per_request: int = 150,
        max_browse_depth: int = 4
    ):
        self.default_timeout_sec = default_timeout_sec
        self.max_nodes_per_request = max_nodes_per_request
        self.max_browse_depth = max_browse_depth

    # =========================================================================
    # 1. BROWSE ROOT / OBJECTS FOLDER
    # =========================================================================

    async def browse_root(
        self,
        client: SecureOPCUAClient,
        max_depth: Optional[int] = None,
        max_nodes: Optional[int] = None,
        filter_system_nodes: bool = True
    ) -> List[DiscoveredTag]:
        """Browse the root Objects folder (`ns=0;i=85`) down to a bounded depth."""
        if not client._client:
            raise OPCUAError("Cannot browse address space: OPC UA client is not connected.")

        depth_limit = min(max_depth or self.max_browse_depth, self.max_browse_depth)
        node_limit = min(max_nodes or self.max_nodes_per_request, self.max_nodes_per_request)

        objects_node = client._client.nodes.objects
        visited: Set[str] = set()
        count = 0

        async def _browse_recursive(node: Node, current_depth: int, parent_id: Optional[str]) -> Optional[DiscoveredTag]:
            nonlocal count
            node_id_str = node.nodeid.to_string()

            # Cycle protection
            if node_id_str in visited or count >= node_limit:
                return None
            visited.add(node_id_str)
            count += 1

            # Extract current node metadata
            tag = await extract_node_metadata(node, parent_node_id=parent_id, timeout_sec=self.default_timeout_sec)

            # Skip standard internal OPC UA server diagnostics if requested
            if filter_system_nodes and tag.browse_name in ("Server", "ServerDiagnostics", "Aliases"):
                return None

            # Recursively explore children up to depth limit
            if current_depth < depth_limit and tag.node_class in ("Object", "Folder"):
                try:
                    children = await asyncio.wait_for(
                        node.get_children(),
                        timeout=self.default_timeout_sec
                    )
                    for child in children:
                        if count >= node_limit:
                            break
                        child_tag = await _browse_recursive(child, current_depth + 1, tag.node_id)
                        if child_tag:
                            tag.children.append(child_tag)
                except Exception as e:
                    logger.debug(f"Could not browse children of {node_id_str}: {e}")

            return tag

        results: List[DiscoveredTag] = []
        try:
            top_level = await asyncio.wait_for(
                objects_node.get_children(),
                timeout=self.default_timeout_sec
            )
            for child in top_level:
                if count >= node_limit:
                    break
                tag = await _browse_recursive(child, current_depth=1, parent_id="ns=0;i=85")
                if tag:
                    results.append(tag)
        except Exception as e:
            logger.error(f"Error browsing root address space: {e}")
            raise OPCUAError(f"Failed to browse root address space: {e}") from e

        return results

    # =========================================================================
    # 2. BROWSE SPECIFIC NODE CHILDREN (LAZY EXPANSION)
    # =========================================================================

    async def browse_children(
        self,
        client: SecureOPCUAClient,
        parent_node_id: str,
        max_nodes: Optional[int] = None
    ) -> List[DiscoveredTag]:
        """Lazy expansion: browse direct children of a specific node."""
        if not client._client:
            raise OPCUAError("Cannot browse node: OPC UA client is not connected.")

        node_limit = min(max_nodes or self.max_nodes_per_request, self.max_nodes_per_request)
        try:
            parent_node = client._client.get_node(parent_node_id)
            children = await asyncio.wait_for(
                parent_node.get_children(),
                timeout=self.default_timeout_sec
            )

            results: List[DiscoveredTag] = []
            for child in children[:node_limit]:
                tag = await extract_node_metadata(
                    child,
                    parent_node_id=parent_node_id,
                    timeout_sec=self.default_timeout_sec
                )
                results.append(tag)

            return results
        except Exception as e:
            logger.error(f"Error browsing children of '{parent_node_id}': {e}")
            raise OPCUAError(f"Failed to browse children for node '{parent_node_id}': {e}") from e

    # =========================================================================
    # 3. GET SINGLE NODE METADATA
    # =========================================================================

    async def get_node_metadata(
        self,
        client: SecureOPCUAClient,
        node_id: str
    ) -> Optional[DiscoveredTag]:
        """Fetch complete metadata for a single specific NodeId."""
        if not client._client:
            raise OPCUAError("Cannot get node metadata: OPC UA client is not connected.")

        try:
            node = client._client.get_node(node_id)
            tag = await extract_node_metadata(node, timeout_sec=self.default_timeout_sec)
            if tag.node_class == "Unknown":
                raise OPCUAError(f"Node '{node_id}' does not exist in the OPC UA address space.")
            return tag
        except Exception as e:
            logger.error(f"Error fetching metadata for '{node_id}': {e}")
            raise OPCUAError(f"Could not retrieve metadata for '{node_id}': {e}") from e

    # =========================================================================
    # 4. SEARCH DISCOVERED TAGS
    # =========================================================================

    async def search_discovered_tags(
        self,
        client: SecureOPCUAClient,
        query: str,
        root_node_id: Optional[str] = None,
        max_results: int = 50
    ) -> List[DiscoveredTag]:
        """Search address space for variables/signals matching a keyword."""
        if not client._client:
            raise OPCUAError("Cannot search tags: OPC UA client is not connected.")

        clean_query = query.strip().lower()
        if not clean_query:
            return []

        # Browse tree and filter matches
        tags = await self.browse_root(
            client,
            max_depth=self.max_browse_depth,
            max_nodes=self.max_nodes_per_request,
            filter_system_nodes=True
        )

        matches: List[DiscoveredTag] = []

        def _traverse(tag_list: List[DiscoveredTag]):
            for t in tag_list:
                if len(matches) >= max_results:
                    return
                # Check match against browse_name, display_name, description, or node_id
                if (
                    clean_query in t.browse_name.lower()
                    or clean_query in t.display_name.lower()
                    or clean_query in (t.description or "").lower()
                    or clean_query in t.node_id.lower()
                ):
                    matches.append(t)
                if t.children:
                    _traverse(t.children)

        _traverse(tags)
        return matches

    # =========================================================================
    # 5. VALIDATE READABLE NODE
    # =========================================================================

    async def validate_readable_node(
        self,
        client: SecureOPCUAClient,
        node_id: str
    ) -> Tuple[bool, Optional[str]]:
        """Verify that a discovered variable node is accessible and readable."""
        if not client._client:
            return False, "Client is not connected"

        try:
            val = await client.read_value(node_id)
            return True, None
        except Exception as e:
            return False, str(e)

