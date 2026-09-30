# HumanVibe Blog Queue State

SOURCE: Shopify Admin GraphQL live read — HumanVibe (kivmp6-mw.myshopify.com)
QUEUE_RULE: maintain at least 2 future scheduled articles on the standing 48-hour editorial cadence
FUTURE_SCHEDULED_COUNT: 1
NEEDS_REFILL: YES
NEXT_DUE_UTC: 2026-10-01T08:00:00Z
BLOG: Our Journey

## Scheduled articles
- 2026-10-01T08:00:00Z | Louisiana Men's Style Guide: Relaxed Outfits for Warm Weekends | gid://shopify/Article/577108213814

GRACE_ACTION_IF_NEEDS_REFILL: Treat the blog queue as operational continuity context. If FUTURE_SCHEDULED_COUNT is below 2, route one bounded blog-refill task through the established HumanVibe content pipeline. Preserve the existing two-day cadence, verify content/CTA/internal-link quality, and physically reread Shopify after scheduling.
