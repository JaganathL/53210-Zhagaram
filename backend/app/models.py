from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=40)
    # Rental categories are priced per day and have no MRP.
    rental: bool = False


class Category(CategoryIn):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    order: int = 0
    created_at: datetime = Field(alias="createdAt")


class CategoryOut(Category):
    item_count: int = Field(default=0, alias="itemCount")


class PartBase(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(min_length=2, max_length=120)
    sku: str = Field(min_length=2, max_length=40)
    category: str = Field(min_length=2, max_length=40)
    brand: str = Field(min_length=1, max_length=60)
    # For rental categories this is the price per day.
    price: float = Field(gt=0, le=10_000_000)
    mrp: float | None = Field(default=None, gt=0, le=10_000_000)
    description: str = Field(default="", max_length=2000)
    specs: dict[str, str] = Field(default_factory=dict)
    image_url: str = Field(
        default="", max_length=300, alias="imageUrl",
        pattern=r"^(|/api/images/[0-9a-f]{32}|https://\S+)$",
    )


class PartCreate(PartBase):
    pass


class PartUpdate(PartBase):
    pass


class Part(PartBase):
    id: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


@dataclass(frozen=True)
class ImageRecord:
    id: str
    content_type: str
    filename: str
    data: bytes
    created_at: datetime


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str = Field(serialization_alias="accessToken")
    token_type: str = Field(default="bearer", serialization_alias="tokenType")
    expires_in: int = Field(serialization_alias="expiresIn")


class UploadResponse(BaseModel):
    image_url: str = Field(serialization_alias="imageUrl")
