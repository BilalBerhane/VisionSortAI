# api/batches.py

from flask import Blueprint, jsonify
import os

from azure.cosmos import CosmosClient  # type: ignore

batches_bp = Blueprint("batches", __name__, url_prefix="/api/batches")


# ---------------------------------------------------------
# Cosmos DB connection
# ---------------------------------------------------------

COSMOS_ENDPOINT = os.getenv("AZURE_COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("AZURE_COSMOS_KEY")
COSMOS_DATABASE = os.getenv("AZURE_COSMOS_DATABASE", "visionsortai")
COSMOS_CONTAINER = os.getenv("AZURE_COSMOS_CONTAINER", "photos")


def get_container():
    client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)

    database = client.get_database_client(COSMOS_DATABASE)

    return database.get_container_client(COSMOS_CONTAINER)


# ---------------------------------------------------------
# GET ALL BATCHES
# ---------------------------------------------------------

@batches_bp.route("/", methods=["GET"])
def get_batches():

    try:
        container = get_container()

        query = """
            SELECT
                c.batch_id,
                COUNT(1) AS total_photos,
                SUM(IIF(c.status = 'approved', 1, 0)) AS approved,
                SUM(IIF(c.status = 'quarantine', 1, 0)) AS quarantined,
                SUM(IIF(c.status = 'review', 1, 0)) AS review
            FROM c
            GROUP BY c.batch_id
        """

        results = list(
            container.query_items(
                query=query,
                enable_cross_partition_query=True
            )
        )

        batches = []

        for item in results:

            batches.append({
                "batch_id": item.get("batch_id"),
                "total_photos": item.get("total_photos", 0),
                "approved": item.get("approved", 0),
                "quarantined": item.get("quarantined", 0),
                "review": item.get("review", 0)
            })

        return jsonify({
            "success": True,
            "batches": batches
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------------------------------------------------------
# GET ONE BATCH
# ---------------------------------------------------------

@batches_bp.route("/<batch_id>", methods=["GET"])
def get_batch(batch_id):

    try:

        container = get_container()

        query = """
            SELECT *
            FROM c
            WHERE c.batch_id = @batch_id
        """

        parameters = [
            {
                "name": "@batch_id",
                "value": batch_id
            }
        ]

        photos = list(
            container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            )
        )

        return jsonify({
            "success": True,
            "batch_id": batch_id,
            "photos": photos,
            "total": len(photos)
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500