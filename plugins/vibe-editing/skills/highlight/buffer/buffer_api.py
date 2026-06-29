"""
Buffer GraphQL API client — post creation + channel discovery.

Targets YOUR configured channel (config.buffer_channel_id()). There is NO hardcoded
channel and NO lock to any specific profile — you choose the channel via
BUFFER_CHANNEL_ID / ~/.config/buffer/channel_id, discoverable with `discover()`.
"""

import json

import requests

from config import BUFFER_API_ENDPOINT, buffer_channel_id, buffer_token


def _gql(query: str, variables: dict | None = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    resp = requests.post(
        BUFFER_API_ENDPOINT,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {buffer_token()}",
        },
        json=payload,
    )

    # Surface rate limits so the caller can back off (see fill_queue retry loop).
    if resp.status_code != 200:
        raise RuntimeError(f"Buffer API error ({resp.status_code}): {resp.text}")

    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")
    return data["data"]


# ── Discovery (read-only) ─────────────────────────────────────────────

def get_account() -> dict:
    data = _gql("""
        query {
            account {
                id
                email
                organizations {
                    id
                    name
                }
            }
        }
    """)
    return data["account"]


def get_channels(org_id: str) -> list[dict]:
    data = _gql(f"""
        query {{
            channels(input: {{ organizationId: "{org_id}" }}) {{
                id
                name
                service
            }}
        }}
    """)
    return data["channels"]


# ── Post Creation (YOUR configured channel) ────────────────────────────

def create_video_post(
    video_url: str,
    text: str,
    title: str,
    channel_id: str | None = None,
    category_id: str = "22",
    privacy: str = "public",
    due_at: str | None = None,
    thumbnail_url: str | None = None,
    notify_subscribers: bool = True,
    made_for_kids: bool = False,
    share_now: bool = False,
) -> dict:
    """Create a video post on YOUR channel via Buffer.

    channel_id defaults to config.buffer_channel_id() (env BUFFER_CHANNEL_ID or
    ~/.config/buffer/channel_id). Pass channel_id explicitly to override per-call.
    """
    target_channel = channel_id or buffer_channel_id()

    video_asset = f'{{ url: "{video_url}"'
    if thumbnail_url:
        video_asset += f', thumbnailUrl: "{thumbnail_url}"'
    video_asset += f', metadata: {{ title: "{_esc(title)}" }}'
    video_asset += " }"

    if share_now:
        mode = "shareNow"
        schedule_line = ""
    elif due_at:
        mode = "customScheduled"
        schedule_line = f', dueAt: "{due_at}"'
    else:
        mode = "addToQueue"
        schedule_line = ""

    mutation = f"""
        mutation CreateVideoPost {{
            createPost(input: {{
                text: "{_esc(text)}",
                channelId: "{target_channel}",
                schedulingType: automatic,
                mode: {mode}
                {schedule_line}
                assets: [{{ video: {video_asset} }}]
                metadata: {{
                    youtube: {{
                        title: "{_esc(title)}",
                        categoryId: "{category_id}",
                        privacy: {privacy},
                        notifySubscribers: {"true" if notify_subscribers else "false"},
                        embeddable: true,
                        madeForKids: {"true" if made_for_kids else "false"}
                    }}
                }}
            }}) {{
                ... on PostActionSuccess {{
                    post {{
                        id
                        text
                        dueAt
                        status
                        assets {{
                            id
                            mimeType
                        }}
                    }}
                }}
                ... on MutationError {{
                    message
                }}
            }}
        }}
    """

    data = _gql(mutation)
    result = data["createPost"]

    if "message" in result:
        raise RuntimeError(f"Buffer post failed: {result['message']}")

    return result["post"]


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


# ── CLI helper: list channels so you can find YOUR channel id ──────────

def discover() -> None:
    """Print every channel on your Buffer account so you can copy the id you want."""
    account = get_account()
    print(f"Account: {account['email']}\n")
    for org in account["organizations"]:
        print(f"Org: {org['name']} (id: {org['id']})")
        channels = get_channels(org["id"])
        for ch in channels:
            print(f"  {ch['service']:12s} | {ch['name']:25s} | id: {ch['id']}")
        print()
    print("Set the channel you want to post to:")
    print("  export BUFFER_CHANNEL_ID='<id-from-above>'")
    print("  (or write it to ~/.config/buffer/channel_id)")
