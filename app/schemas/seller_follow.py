import uuid
from datetime import datetime

from pydantic import BaseModel


class FollowResponse(BaseModel):
    """Response after following/unfollowing a seller."""
    is_following: bool
    followers_count: int
    message: str


class FollowerResponse(BaseModel):
    """A follower's info."""
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class FollowingStatus(BaseModel):
    """Whether the current user follows a seller."""
    is_following: bool
