"""Headless end-to-end check for the link-screening glue (tools/screen.py).

Builds real posts (a live one per ATS + a deliberately-dead one per ATS) by
pulling fresh live ids from each board, then runs screen_posts against a target
locale and prints keep/drop. Substitutes for `adk web` for the fetch+parse+decide
path (no workflow / LLM / SerpAPI needed).

Run: .venv/bin/python -m job_finder.verify_screen
"""

import asyncio

import httpx

from .tools.screen import screen_posts

TARGET = "United States"


async def build_posts():
    posts = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
        # Lever: live palantir posting + a bogus (dead) id
        lev = (await c.get("https://api.lever.co/v0/postings/palantir?mode=json&limit=1")).json()[0]
        posts.append({"label": "lever LIVE", "url": lev["hostedUrl"], "id": lev["id"]})
        posts.append({"label": "lever DEAD", "url": "https://jobs.lever.co/palantir/00000000-0000-0000-0000-000000000000", "id": "00000000-0000-0000-0000-000000000000"})

        # Greenhouse: live discord job + bogus id
        gh = (await c.get("https://boards-api.greenhouse.io/v1/boards/discord/jobs")).json()["jobs"][0]
        posts.append({"label": "greenhouse LIVE", "url": f"https://boards.greenhouse.io/discord/jobs/{gh['id']}", "id": str(gh["id"])})
        posts.append({"label": "greenhouse DEAD", "url": "https://boards.greenhouse.io/discord/jobs/1", "id": "1"})

        # Ashby: a US (in-locale) openai job + a non-US one + bogus id
        ashby = (await c.get("https://api.ashbyhq.com/posting-api/job-board/openai")).json()["jobs"]
        us = next((j for j in ashby if (j.get("address") or {}).get("postalAddress", {}).get("addressCountry") == "United States"), ashby[0])
        non_us = next((j for j in ashby if (j.get("address") or {}).get("postalAddress", {}).get("addressCountry") not in ("United States", None)), None)
        posts.append({"label": "ashby US", "url": us["jobUrl"], "id": us["id"]})
        if non_us:
            posts.append({"label": f"ashby {non_us['address']['postalAddress']['addressCountry']}", "url": non_us["jobUrl"], "id": non_us["id"]})
        posts.append({"label": "ashby DEAD", "url": "https://jobs.ashbyhq.com/openai/00000000-0000-0000-0000-000000000000", "id": "00000000-0000-0000-0000-000000000000"})
    return posts


async def main():
    posts = await build_posts()
    survivors = await screen_posts(posts, TARGET)
    kept_ids = {p["id"] for p in survivors}
    print(f"target locale: {TARGET!r}\n")
    for p in posts:
        verdict = "KEEP" if p["id"] in kept_ids else "drop"
        print(f"  [{verdict}]  {p['label']:24}  {p['url']}")
    print(f"\n{len(posts)} posts -> {len(survivors)} survivors")


if __name__ == "__main__":
    asyncio.run(main())
