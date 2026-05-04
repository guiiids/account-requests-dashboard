from app import app
import database

with app.test_request_context():
    reqs = database.get_all_requests(
        statuses=['Closed - Resolved']
    )
    print("Closed Resolved count:", len(reqs))
