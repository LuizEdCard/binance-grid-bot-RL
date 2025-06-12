# /home/ubuntu/backend_consolidated/src/utils/social_listener.py

import os
import random  # Import random for mocking

import praw
from dotenv import load_dotenv

from .logger import log

# Load environment variables from .env file in the secrets directory
dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", "secrets", ".env")
load_dotenv(dotenv_path=dotenv_path)


class SocialListener:
    """Connects to Reddit API using PRAW to fetch posts and comments.
    Includes MOCKING for testing without real credentials.
    """

    def __init__(self, mock_mode=False):
        self.reddit = None
        self.mock_mode = mock_mode
        if not self.mock_mode:
            self._authenticate()
        else:
            log.warning(
                "SocialListener running in MOCK MODE. No real Reddit API calls will be made."
            )

    def _authenticate(self):
        # ... (authentication logic remains the same) ...
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv(
            "REDDIT_USER_AGENT",
            "python:gridtradingbot:v0.1 (by u/your_reddit_username)",
        )
        if not client_id or not client_secret:
            log.error("Reddit API credentials not found. Cannot authenticate.")
            return
        try:
            log.info("Authenticating with Reddit API...")
            self.reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
                read_only=True,
            )
            self.reddit.user.me()
            log.info("Reddit API authentication successful (read-only mode).")
        except Exception as e:
            log.error(f"Failed to authenticate with Reddit API: {e}", exc_info=True)
            self.reddit = None

    def get_subreddit_posts(
        self, subreddit_name: str, limit: int = 10, time_filter: str = "day"
    ) -> list[dict]:
        if self.mock_mode:
            log.info(f"[MOCK] Fetching {limit} posts from r/{subreddit_name}")
            mock_posts = []
            sentiment_options = [
                "amazing opportunity!",
                "going to the moon!",
                "great potential",
                "looks stable",
                "uncertain times",
                "sell now!",
                "market crash imminent",
                "terrible investment",
            ]
            for i in range(limit):
                mock_posts.append(
                    {
                        "id": f"mock_post_{i}_{subreddit_name}",
                        "title": f"Mock Post {i+1} from {subreddit_name}",
                        "selftext": f"This is mock content about {subreddit_name}. Sentiment: {random.choice(sentiment_options)}",
                        "score": random.randint(1, 1000),
                        "url": f"http://mock.reddit.com/{subreddit_name}/post_{i}",
                    }
                )
            return mock_posts

        if not self.reddit:
            log.error("Reddit API not authenticated. Cannot fetch posts.")
            return []
        # ... (real fetching logic remains the same) ...
        posts_data = []
        try:
            log.info(
                f"Fetching top {limit} posts from r/{subreddit_name} (time_filter={time_filter})..."
            )
            subreddit = self.reddit.subreddit(subreddit_name)
            for post in subreddit.top(time_filter=time_filter, limit=limit):
                posts_data.append(
                    {
                        "id": post.id,
                        "title": post.title,
                        "selftext": post.selftext,
                        "score": post.score,
                        "url": post.url,
                    }
                )
            log.info(f"Fetched {len(posts_data)} posts from r/{subreddit_name}.")
        except Exception as e:
            log.error(
                f"Error fetching posts from r/{subreddit_name}: {e}", exc_info=True
            )
        return posts_data

    def get_post_comments(self, post_id: str, limit: int = 20) -> list[str]:
        if self.mock_mode:
            log.info(f"[MOCK] Fetching {limit} comments for post {post_id}")
            mock_comments = []
            sentiment_options = [
                "Totally agree!",
                "This is the way.",
                "Interesting point.",
                "Not sure about that.",
                "I disagree completely.",
                "This is FUD.",
                "Scam alert!",
            ]
            for i in range(limit):
                mock_comments.append(
                    f"Mock comment {i+1} for post {post_id}. Sentiment: {random.choice(sentiment_options)}"
                )
            return mock_comments

        if not self.reddit:
            log.error("Reddit API not authenticated. Cannot fetch comments.")
            return []
        # ... (real fetching logic remains the same) ...
        comments_data = []
        try:
            log.info(f"Fetching comments for post ID: {post_id} (limit={limit})...")
            submission = self.reddit.submission(id=post_id)
            submission.comment_sort = "top"
            submission.comments.replace_more(limit=0)
            count = 0
            for comment in submission.comments:
                if count >= limit:
                    break
                if isinstance(comment, praw.models.Comment):
                    comments_data.append(comment.body)
                    count += 1
            log.info(f"Fetched {len(comments_data)} comments for post {post_id}.")
        except Exception as e:
            log.error(f"Error fetching comments for post {post_id}: {e}", exc_info=True)
        return comments_data


# Example Usage (can now run with mock_mode=True without .env)
if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    log.setLevel(logging.INFO)

    print("Initializing SocialListener in MOCK MODE...")
    listener = SocialListener(mock_mode=True)

    print("\nFetching mock posts from r/investing...")
    posts = listener.get_subreddit_posts("investing", limit=3)
    if posts:
        print(f"Found {len(posts)} mock posts.")
        for i, post in enumerate(posts):
            print(f"  Post {i+1}: {post['title'][:80]}...")
            print(f"    Text: {post['selftext'][:100]}...")
            if i == 0:
                print(f"\nFetching mock comments for post ID: {post['id']}...")
                comments = listener.get_post_comments(post["id"])
                if comments:
                    print(f"Found {len(comments)} mock comments:")
                    for j, comment_body in enumerate(comments):
                        print(f"    Comment {j+1}: {comment_body[:100]}...")
                else:
                    print("Could not fetch mock comments.")
    else:
        print("Could not fetch mock posts.")
