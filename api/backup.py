# api/backup.py

from flask import Blueprint, jsonify
import os
from datetime import datetime

from azure.cosmos import CosmosClient  # type: ignore
from azure.storage.blob import BlobServiceClient

backup_bp = Blueprint(
    "backup",
    __name__,
    url_prefix="/api/backup"
)


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

APPROVED_CONTAINER = os.getenv(
    "AZURE_APPROVED_CONTAINER",
    "approved"
)

BACKUP_CONTAINER = os.getenv(
    "AZURE_BACKUP_CONTAINER",
    "backup"
)


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


def get_blob_service():

    return BlobServiceClient.from_connection_string(
        STORAGE_CONNECTION
    )


# ---------------------------------------------------------
# GET BACKED UP PHOTOS
# ---------------------------------------------------------

@backup_bp.route("/", methods=["GET"])
def get_backups():

    try:

        container = get_cosmos_container()

        query = """
            SELECT *
            FROM c
            WHERE IS_DEFINED(c.backup_at)
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
            "backups": photos,
            "total": len(photos)
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------------------------------------------------------
# BACKUP ONE PHOTO
# ---------------------------------------------------------

@backup_bp.route("/<photo_id>", methods=["POST"])
def backup_photo(photo_id):

    try:

        cosmos = get_cosmos_container()

        query = """
            SELECT *
            FROM c
            WHERE c.id = @id
        """

        results = list(
            cosmos.query_items(
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

        filename = photo.get("filename")

        if not filename:

            return jsonify({
                "success": False,
                "error": "Photo filename missing"
            }), 400

        blob_service = get_blob_service()

        source_blob = blob_service.get_blob_client(
            container=APPROVED_CONTAINER,
            blob=filename
        )

        destination_blob = blob_service.get_blob_client(
            container=BACKUP_CONTAINER,
            blob=filename
        )

        destination_blob.start_copy_from_url(
            source_blob.url
        )

        photo["backup_at"] = datetime.utcnow().isoformat()

        photo["backup_status"] = "completed"

        cosmos.upsert_item(photo)

        return jsonify({
            "success": True,
            "message": "Photo backed up successfully",
            "photo": photo
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500