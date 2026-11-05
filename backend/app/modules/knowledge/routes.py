"""Flask routes for Technical Knowledge, SOPs, and Semantic Vector Retrieval."""
from flask import Blueprint, request, jsonify, g
from app.security.decorators import login_required
from app.modules.knowledge.services import KnowledgeService

knowledge_bp = Blueprint("knowledge", __name__)


@knowledge_bp.route("/knowledge/documents", methods=["GET"])
@login_required
def list_documents():
    """Lists accessible SOPs, technical manuals, and OEM bulletins."""
    org_id = g.current_org_id
    doc_type = request.args.get("document_type")
    machine_type = request.args.get("machine_type")
    limit = request.args.get("limit", 100, type=int)

    try:
        docs = KnowledgeService.list_documents(
            organization_id=org_id,
            document_type=doc_type,
            machine_type=machine_type,
            limit=limit,
        )
        return jsonify(docs), 200
    except Exception as e:
        return jsonify({"error": f"Failed to list documents: {str(e)}"}), 500


@knowledge_bp.route("/knowledge/documents", methods=["POST"])
@login_required
def create_document():
    """Indexes and vectorizes a new technical document."""
    org_id = g.current_org_id
    data = request.get_json(silent=True) or {}

    title = data.get("title")
    content = data.get("content")
    if not title or not content:
        return jsonify({"error": "title and content are required"}), 400

    doc_type = data.get("document_type", "SOP")
    machine_type = data.get("machine_type")
    component_type = data.get("component_type")
    is_standard = bool(data.get("is_standard", False))
    doc_meta = data.get("metadata")

    try:
        result = KnowledgeService.create_document(
            organization_id=org_id,
            title=title,
            document_type=doc_type,
            content=content,
            machine_type=machine_type,
            component_type=component_type,
            is_standard=is_standard,
            document_metadata=doc_meta,
        )
        return jsonify(result), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to create document: {str(e)}"}), 500


@knowledge_bp.route("/knowledge/documents/<string:doc_id>", methods=["GET"])
@login_required
def get_document(doc_id):
    """Retrieves document metadata and indexed chunks."""
    org_id = g.current_org_id
    try:
        doc = KnowledgeService.get_document(doc_id, org_id)
        return jsonify(doc), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve document: {str(e)}"}), 500


@knowledge_bp.route("/knowledge/retrieve-test", methods=["POST"])
@login_required
def test_retrieval():
    """Tests semantic vector similarity search against technical documentation."""
    org_id = g.current_org_id
    data = request.get_json(silent=True) or {}

    query = data.get("query")
    if not query:
        return jsonify({"error": "query is required"}), 400

    machine_type = data.get("machine_type")
    component_type = data.get("component_type")
    top_k = data.get("top_k", 5)

    try:
        results = KnowledgeService.test_retrieval(
            organization_id=org_id,
            query=query,
            machine_type=machine_type,
            component_type=component_type,
            top_k=top_k,
        )
        return jsonify(results), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to test retrieval: {str(e)}"}), 500

