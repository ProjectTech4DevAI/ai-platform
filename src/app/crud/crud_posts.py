from fastcrud import FastCRUD

from ..models.post import Post
from ..schemas.post import PostCreateInternal, PostDelete, PostUpdate, PostUpdateInternal, PostRead

CRUDPost = FastCRUD[Post, PostCreateInternal,
                    PostUpdate, PostUpdateInternal, PostDelete, PostRead]
crud_posts = CRUDPost(Post)
