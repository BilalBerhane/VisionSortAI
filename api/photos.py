# api/photos.py

from flask import Blueprint, jsonify, request
import os

from azure.cosmos import CosmosClient  # type: ignore

photos_bp = Blueprint("photos", __name__, url_prefix="/api/photos")


COSMOS_ENDPOINT = os.getenv("AZURE_COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("AZURE_COSMOS_KEY")
COSMOS_DATABASE = os.getenv("AZURE_COSMOS_DATABASE", "visionsortai")
COSMOS_CONTAINER = os.getenv("AZURE_COSMOS_CONTAINER", "photos")


def get_container():

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
# GET PHOTOS
# ---------------------------------------------------------

@photos_bp.route("/", methods=["GET"])
def get_photos():

    try:

        container = get_container()

        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 20))

        batch_id = request.args.get("batch_id")
        status = request.args.get("status")

        conditions = []
        parameters = []

        if batch_id:

            conditions.append(
                "c.batch_id = @batch_id"
            )

            parameters.append({
                "name": "@batch_id",
                "value": batch_id
            })

        if status:

            conditions.append(
                "c.status = @status"
            )

            parameters.append({
                "name": "@status",
                "value": status
            })

        where_clause = ""

        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT *
            FROM c
            {where_clause}
            ORDER BY c._ts DESC
        """

        all_photos = list(
            container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            )
        )

        start = (page - 1) * limit
        end = start + limit

        photos = all_photos[start:end]

        return jsonify({

            "success": True,

            "page": page,

            "limit": limit,

            "total": len(all_photos),

            "pages": (
                (len(all_photos) + limit - 1) // limit
            ),

            "photos": photos

        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------------------------------------------------------
# GET ONE PHOTO
# ---------------------------------------------------------

@photos_bp.route("/<photo_id>", methods=["GET"])
def get_photo(photo_id):

    try:

        container = get_container()

        query = """
            SELECT *
            FROM c
            WHERE c.id = @photo_id
        """

        parameters = [
            {
                "name": "@photo_id",
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

        return jsonify({
            "success": True,
            "photo": results[0]
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500