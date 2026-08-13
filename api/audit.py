# api/audit.py

from flask import Blueprint, jsonify, request
import os
from datetime import datetime
import uuid

from azure.cosmos import CosmosClient  # type: ignore

audit_bp = Blueprint(
    "audit",
    __name__,
    url_prefix="/api/audit"
)


COSMOS_ENDPOINT = os.getenv("AZURE_COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("AZURE_COSMOS_KEY")

COSMOS_DATABASE = os.getenv(
    "AZURE_COSMOS_DATABASE",
    "visionsortai"
)

AUDIT_CONTAINER = os.getenv(
    "AZURE_AUDIT_CONTAINER",
    "audit"
)


def get_audit_container():

    client = CosmosClient(
        COSMOS_ENDPOINT,
        COSMOS_KEY
    )

    database = client.get_database_client(
        COSMOS_DATABASE
    )

    return database.get_container_client(
        AUDIT_CONTAINER
    )


# ---------------------------------------------------------
# GET AUDIT LOG
# ---------------------------------------------------------

@audit_bp.route("/", methods=["GET"])
def get_audit_logs():

    try:

        container = get_audit_container()

        limit = int(
            request.args.get("limit", 100)
        )

        query = f"""
            SELECT TOP {limit} *
            FROM c
            ORDER BY c.timestamp DESC
        """

        logs = list(
            container.query_items(
                query=query,
                enable_cross_partition_query=True
            )
        )

        return jsonify({
            "success": True,
            "logs": logs
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------------------------------------------------------
# CREATE AUDIT LOG
# ---------------------------------------------------------

@audit_bp.route("/", methods=["POST"])
def create_audit_log():

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "error": "JSON body required"
            }), 400

        container = get_audit_container()

        audit = {

            "id": str(uuid.uuid4()),

            "action": data.get(
                "action",
                "unknown"
            ),

            "photo_id": data.get(
                "photo_id"
            ),

            "batch_id": data.get(
                "batch_id"
            ),

            "user": data.get(
                "user",
                "system"
            ),

            "details": data.get(
                "details",
                ""
            ),

            "timestamp":
                datetime.utcnow().isoformat()

        }

        container.create_item(
            body=audit
        )

        return jsonify({

            "success": True,

            "message":
                "Audit event recorded",

            "audit": audit

        }), 201

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500