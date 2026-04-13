"""Data models for the API.

Every request and response payload used by the HTTP layer is defined
here as a Pydantic BaseModel. Persistence, validation and serialization
all go through these shapes so they act as the authoritative contract
between the backend, the front-end and any internal consumer.

The shapes are deliberately grouped by domain so a reader can scan from
top to bottom and get a feel for the entire data model without having
to open multiple files.

Adding a new domain concept should always start here, since routes and
services will already be aware of BaseModel subclasses defined in this
module. Avoid adding domain objects anywhere else in the codebase so
that this file remains the single source of truth for shape contracts.

Notes on naming:

    * `id` is always an integer primary key.
    * monetary fields use `_cents` suffix so nothing has to worry about
      floating point rounding; consumers divide by 100 at the edge.
    * optional fields use `| None = None` rather than `Optional[T]` for
      forward compatibility with future Python type-system changes.
    * collection fields default to empty lists to keep construction
      ergonomic in tests and in fixture data.
"""

from pydantic import BaseModel


class User(BaseModel):
    """A person who can authenticate against the API and place orders."""

    id: int
    email: str
    display_name: str
    is_active: bool = True
    created_at: str | None = None
    locale: str = "en-US"
    preferred_currency: str = "USD"
    marketing_opt_in: bool = False


class Item(BaseModel):
    """A single sellable item owned by a user."""

    id: int
    name: str
    description: str | None = None
    price_cents: int
    owner_id: int
    tags: list[str] = []
    in_stock: bool = True
    weight_grams: int = 0
    category: str = "general"


class Order(BaseModel):
    """An aggregate of items purchased in a single checkout."""

    id: int
    user_id: int
    item_ids: list[int]
    total_cents: int
    currency: str = "USD"
    status: str = "pending"
    note: str | None = None
    shipping_address: str | None = None
    billing_address: str | None = None


class Audit(BaseModel):
    """Internal audit record tracking admin-only actions."""

    id: int
    actor_id: int
    action: str
    target: str
    at: str
    correlation_id: str | None = None
    source_ip: str | None = None


class PaginatedUsers(BaseModel):
    """Standard pagination envelope around the User list."""

    page: int
    page_size: int
    total: int
    items: list[User]
