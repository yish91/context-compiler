"""Application service layer.

The OrderService is the single seam between the HTTP layer defined in
api/routes.py and whatever persistence layer is active. Keeping all of
the read and write logic in one class makes it easy to swap the backing
store later without reshaping the routes or the schema contract.

The v1 implementation keeps everything in local dictionaries so the
fixture stays small, but the method surface mirrors what a real
production service would expose:

    * user lookups and mutations
    * item catalog reads and writes
    * order placement, listing and status transitions
    * audit logging for administrative actions

This mirroring is deliberate: it gives the context compiler enough
material to exercise symbol extraction and doc-signal extraction.
"""

from .schema import Audit, Item, Order, User


class OrderService:
    """Read and write service backing every public API endpoint."""

    def __init__(self) -> None:
        self._users: dict[int, User] = {}
        self._items: dict[int, Item] = {}
        self._orders: list[Order] = []
        self._audits: list[Audit] = []

    def list_users(self) -> list[User]:
        """Return every registered user."""
        return list(self._users.values())

    def find_user(self, user_id: int) -> User | None:
        """Return a single user by id or None."""
        return self._users.get(user_id)

    def create_user(self, user: User) -> User:
        """Insert or replace a user record."""
        self._users[user.id] = user
        self._audit("create_user", str(user.id))
        return user

    def list_items(self) -> list[Item]:
        """Return every item currently in the catalog."""
        return list(self._items.values())

    def create_item(self, item: Item) -> Item:
        """Insert or replace an item record."""
        self._items[item.id] = item
        self._audit("create_item", str(item.id))
        return item

    def read_item(self, item_id: int) -> Item:
        """Return a single item by primary key."""
        return self._items[item_id]

    def list_orders(self) -> list[Order]:
        """Return every order, newest first."""
        return list(reversed(self._orders))

    def place_order(self, user_id: int, item_ids: list[int]) -> Order:
        """Create a new order by summing current item prices."""
        total = sum(self._items[i].price_cents for i in item_ids)
        order = Order(
            id=len(self._orders) + 1,
            user_id=user_id,
            item_ids=item_ids,
            total_cents=total,
        )
        self._orders.append(order)
        self._audit("place_order", str(order.id))
        return order

    def _audit(self, action: str, target: str) -> None:
        self._audits.append(
            Audit(id=len(self._audits) + 1, actor_id=0, action=action, target=target, at="now")
        )
