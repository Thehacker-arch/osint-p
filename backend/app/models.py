from pydantic import BaseModel # type: ignore
from typing import List, Optional

class Link(BaseModel):
    url: str

class Person(BaseModel):
    id: str
    username: str
    emails: List[str] = []
    name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    links: List[Link] = []

class SocialMediaProfile(BaseModel):
    platform: str
    username: str
    followers: Optional[int] = None
    following: Optional[int] = None
    posts: Optional[int] = None

class SearchResult(BaseModel):
    person: Person
    profiles: List[SocialMediaProfile] = []
    links: List[Link] = []