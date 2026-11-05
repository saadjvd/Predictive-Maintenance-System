import asyncio
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import asyncua
from asyncua import ua, Node


@dataclass
class DiscoveredTag:
    """Normalized metadata for a discovered OPC UA node in the address space."""
    node_id: str
    browse_name: str
    display_name: str
    node_class: str
    data_type: Optional[str] = None
    engineering_unit: Optional[str] = None
    description: Optional[str] = None
    access_level: Optional[int] = None
    namespace: int = 0
    parent_node_id: Optional[str] = None
    readable: bool = True
    writable: bool = False  # Strictly False by default in PharmaPredict AI
    has_children: bool = False
    children: List['DiscoveredTag'] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "browse_name": self.browse_name,
            "display_name": self.display_name,
            "node_class": self.node_class,
            "data_type": self.data_type,
            "engineering_unit": self.engineering_unit,
            "description": self.description,
            "access_level": self.access_level,
            "namespace": self.namespace,
            "parent_node_id": self.parent_node_id,
            "readable": self.readable,
            "writable": self.writable,
            "has_children": self.has_children,
            "children": [c.to_dict() for c in self.children] if self.children else [],
        }


# Mapping standard OPC UA Data Type NodeIds to human-readable names
STANDARD_DATA_TYPES = {
    1: "Boolean",
    2: "SByte",
    3: "Byte",
    4: "Int16",
    5: "UInt16",
    6: "Int32",
    7: "UInt32",
    8: "Int64",
    9: "UInt64",
    10: "Float",
    11: "Double",
    12: "String",
    13: "DateTime",
    14: "Guid",
    15: "ByteString",
    16: "XmlElement",
    17: "NodeId",
    18: "ExpandedNodeId",
    19: "StatusCode",
    20: "QualifiedName",
    21: "LocalizedText",
    22: "Structure",
    23: "DataValue",
    24: "BaseDataType",
    25: "DiagnosticInfo",
    26: "Number",
    27: "Integer",
    28: "UInteger",
    29: "Enumeration",
}


async def extract_node_metadata(
    node: Node,
    parent_node_id: Optional[str] = None,
    timeout_sec: float = 3.0
) -> DiscoveredTag:
    """Extract complete available OPC UA metadata from a live node without fabricating missing values."""
    node_id_str = node.nodeid.to_string()
    namespace_idx = node.nodeid.NamespaceIndex

    # 1. Browse Name & Display Name
    try:
        browse_name_obj = await asyncio.wait_for(node.read_browse_name(), timeout=timeout_sec)
        browse_name = browse_name_obj.Name if browse_name_obj else node_id_str
    except Exception:
        browse_name = node_id_str

    try:
        display_name_obj = await asyncio.wait_for(node.read_display_name(), timeout=timeout_sec)
        display_name = display_name_obj.Text if display_name_obj else browse_name
    except Exception:
        display_name = browse_name

    # 2. Node Class
    try:
        node_class_val = await asyncio.wait_for(node.read_node_class(), timeout=timeout_sec)
        node_class_name = node_class_val.name if hasattr(node_class_val, "name") else str(node_class_val)
    except Exception:
        node_class_name = "Unknown"

    # 3. Description
    description = None
    try:
        desc_obj = await asyncio.wait_for(node.read_description(), timeout=timeout_sec)
        if desc_obj and hasattr(desc_obj, "Text") and desc_obj.Text:
            description = desc_obj.Text
    except Exception:
        pass

    # 4. Variable-specific attributes (Data Type, Access Level, Engineering Units)
    data_type_name = None
    access_level_val = None
    readable = True
    writable = False
    engineering_unit = None

    if node_class_name == "Variable":
        # Data Type
        try:
            dt_nodeid = await asyncio.wait_for(node.read_data_type(), timeout=timeout_sec)
            if dt_nodeid and dt_nodeid.NamespaceIndex == 0 and dt_nodeid.Identifier in STANDARD_DATA_TYPES:
                data_type_name = STANDARD_DATA_TYPES[dt_nodeid.Identifier]
            else:
                data_type_name = dt_nodeid.to_string() if dt_nodeid else None
        except Exception:
            pass

        # Access Level
        try:
            access_level_val = await asyncio.wait_for(node.read_access_level(), timeout=timeout_sec)
            if isinstance(access_level_val, (int, ua.AccessLevel)):
                # Bit 0 = CurrentRead (1), Bit 1 = CurrentWrite (2)
                raw_int = int(access_level_val)
                readable = bool(raw_int & 1)
                writable = False  # Strictly read-only in PharmaPredict AI
        except Exception:
            pass

        # Engineering Unit (optional OPC UA property: ns=0;i=2362 EUInformation)
        try:
            for child in await node.get_children():
                c_browse = await child.read_browse_name()
                if c_browse.Name in ("EngineeringUnits", "EURange"):
                    eu_val = await child.read_value()
                    if hasattr(eu_val, "DisplayName") and hasattr(eu_val.DisplayName, "Text"):
                        engineering_unit = eu_val.DisplayName.Text
                    elif hasattr(eu_val, "UnitId"):
                        engineering_unit = str(eu_val.UnitId)
                    elif isinstance(eu_val, str):
                        engineering_unit = eu_val
                    break
        except Exception:
            pass

    # Check if node has children
    has_children = False
    try:
        children = await node.get_children()
        has_children = len(children) > 0
    except Exception:
        pass

    return DiscoveredTag(
        node_id=node_id_str,
        browse_name=browse_name,
        display_name=display_name,
        node_class=node_class_name,
        data_type=data_type_name,
        engineering_unit=engineering_unit,
        description=description,
        access_level=access_level_val,
        namespace=namespace_idx,
        parent_node_id=parent_node_id,
        readable=readable,
        writable=writable,
        has_children=has_children,
    )

