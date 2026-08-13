# api/quarantine.py

from flask import Blueprint, jsonify
import os
from datetime import datetime

from azure.cosmos import CosmosClient  # type: ignore
from azure.storage.blob import BlobServiceClient

quarantine_bp = Blueprint(
    "quarantine",
    __name__,
    url_prefix="/api/quarantine"
)


# ---------------------------------------------------------
# Azure configuration
# ---------------------------------------------------------

COSMOS_ENDPOINT = os.getenv("AZURE_COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("AZURE_COSMOS_KEY")
COSMOS_DATABASE = os.getenv(
    "AZURE_COSMOS_DATABASE",
    "visionsortai"
)

COSMOS_CONTAINER = os.getenv(
    "AZURE_COSMOS_CONTAINER",
    "photos"
)

STORAGE_CONNECTION = os.getenv(
    "AZURE_STORAGE_CONNECTION_STRING"
)

QUARANTINE_CONTAINER = os.getenv(
    "AZURE_QUARANTINE_CONTAINER",
    "quarantine"
)

APPROVED_CONTAINER = os.getenv(
    "AZURE_APPROVED_CONTAINER",
    "approved"
)


# ---------------------------------------------------------
# Cosmos helper
# ---------------------------------------------------------

def get_cosmos_container():

    client = CosmosClient(
        COSMOS_ENDPOINT,
        COSMOS_KEY
    )

    database = client.get_database_client(
        COSMOS_DATABASE
    )

    return database.get_container_client(
        COSMOS_CONTAINER
    )


# ---------------------------------------------------------
# Blob helper
# ---------------------------------------------------------

def get_blob_service():

    return BlobServiceClient.from_connection_string(
        STORAGE_CONNECTION
    )


# ---------------------------------------------------------
# GET QUARANTINED PHOTOS
# ---------------------------------------------------------

@quarantine_bp.route("/", methods=["GET"])
def get_quarantine():

    try:

        container = get_cosmos_container()

        query = """
            SELECT *
            FROM c
            WHERE c.status = 'quarantine'
            ORDER BY c._ts DESC
        """

        photos = list(
            container.query_items(
                query=query,
                enable_cross_partition_query=True
            )
        )

        return jsonify({
            "success": True,
            "photos": photos,
            "total": len(photos)
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------------------------------------------------------
# APPROVE PHOTO
# ---------------------------------------------------------

@quarantine_bp.route("/<photo_id>/approve", methods=["POST"])
def approve_photo(photo_id):

    try:

        container = get_cosmos_container()

        query = """
            SELECT *
            FROM c
            WHERE c.id = @id
        """

        parameters = [
            {
                "name": "@id",
                "value": photo_id
            }
        ]

        results = list(
            container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            )
        )

        if not results:

            return jsonify({
                "success": False,
                "error": "Photo not found"
            }), 404

        photo = results[0]

        photo["status"] = "approved"

        photo["approved_at"] = datetime.utcnow().isoformat()

        container.upsert_item(photo)

        return jsonify({
            "success": True,
            "message": "Photo approved",
            "photo": photo
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------------------------------------------------------
# RESTORE PHOTO
# ---------------------------------------------------------

@quarantine_bp.route("/<photo_id>/restore", methods=["POST"])
def restore_photo(photo_id):

    try:

        container = get_cosmos_container()

        query = """
            SELECT *
            FROM c
            WHERE c.id = @id
        """

        results = list(
            container.query_items(
                query=query,
                parameters=[
                    {
                        "name": "@id",
                        "value": photo_id
                    }
                ],
                enable_cross_partition_query=True
            )
        )

        if not results:

            return jsonify({
                "success": False,
                "error": "Photo not found"
            }), 404

        photo = results[0]

        photo["status"] = "review"

        photo["restored_at"] = datetime.utcnow().isoformat()

        container.upsert_item(photo)

        return jsonify({
            "success": True,
            "message": "Photo restored for review",
            "photo": photo
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------------------------------------------------------
# DELETE PHOTO
# ---------------------------------------------------------

@quarantine_bp.route("/<photo_id>", methods=["DELETE"])
def delete_photo(photo_id):

    try:

        container = get_cosmos_container()

        query = """
            SELECT *
            FROM c
            WHERE c.id = @id
        """

        results = list(
            container.query_items(
                query=query,
                parameters=[
                    {
                        "name": "@id",
                        "value": photo_id
                    }
                ],
                enable_cross_partition_query=True
            )
        )

        if not results:

            return jsonify({
                "success": False,
                "error": "Photo not found"
            }), 404

        photo = results[0]

        partition_key = photo.get(
            "batch_id",
            photo_id
        )

        container.delete_item(
            item=photo_id,
            partition_key=partition_key
        )

        return jsonify({
            "success": True,
            "message": "Photo deleted"
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500