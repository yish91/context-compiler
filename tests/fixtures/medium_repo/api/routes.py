"""HTTP route handlers for the API.

This module wires every public endpoint into the FastAPI app. It is the
single entry point for API routing, so most onboarding reads will start
here to learn which endpoints exist and which service methods back them.

Routes are grouped into three domains:
    * health and readiness probes used by the load balancer
    * user-facing endpoints used by the React front-end
    * internal item and order endpoints consumed by the admin UI

Each endpoint body intentionally stays thin; the OrderService class in
api/service.py owns the actual business logic and persistence details.
This keeps route functions easy to understand when someone is trying to
orient themselves to the code base.

When adding a new route, follow the existing pattern:

    1. Accept already-validated Pydantic shapes from api/schema.py.
    2. Delegate to a named OrderService method rather than inlining logic.
    3. Raise HTTPException with a clear status for every failure mode.
    4. Keep the docstring short and answer the question "what does this
       endpoint do" in one sentence so the context compiler can capture
       it as a doc signal.

Routes intentionally live in a single file to make the entire API
surface reviewable in one read. Splitting handlers across multiple
modules is discouraged until the file grows past a few hundred lines.
"""

from fastapi import FastAPI, HTTPException

from .schema import Item, Order, User
from .service import OrderService


def register_routes(app: FastAPI) -> None:
    """Register every public HTTP route against the provided FastAPI app."""

    service = OrderService()

    @app.get("/health")
    def health() -> dict[str, str]:
        """Return a simple liveness response for load balancer health checks."""
        return {"ok": "true"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        """Return readiness so orchestrators know the service can accept traffic."""
        return {"ready": "true"}

    @app.get("/users")
    def list_users() -> list[User]:
        """List every known user. Used by the admin UI user table."""
        return service.list_users()

    @app.get("/users/{user_id}")
    def read_user(user_id: int) -> User:
        """Return a single user by primary key or raise HTTPException(404)."""
        user = service.find_user(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        return user

    @app.post("/items")
    def create_item(item: Item) -> Item:
        """Create or upsert an item in the catalog."""
        return service.create_item(item)

    @app.get("/items")
    def list_items() -> list[Item]:
        """Return every item currently in the catalog."""
        return service.list_items()

    @app.get("/items/{item_id}")
    def read_item(item_id: int) -> Item:
        """Return a single item by primary key."""
        return service.read_item(item_id)

    @app.post("/orders")
    def place_order(user_id: int, item_ids: list[int]) -> Order:
        """Create a new order for the given user and item list."""
        return service.place_order(user_id, item_ids)

    @app.get("/orders")
    def list_orders() -> list[Order]:
        """Return every order, most recent first."""
        return service.list_orders()
