import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories.posts import get_selected_posts
from app.db.session import SessionLocal, init_db
from app.utils.text import shorten_text


def main() -> None:
    init_db()
    with SessionLocal() as session:
        posts = get_selected_posts(session)

    if not posts:
        print("No selected posts.")
        return

    for post in posts:
        category = post.category or "uncategorized"
        print(f"[{post.id}] @{post.source_channel.username} #{post.telegram_message_id} [{category}]")
        print(f"  {shorten_text(post.text, max_length=220)}")
        if post.editor_note:
            print(f"  note: {post.editor_note}")
        print("")


if __name__ == "__main__":
    main()
