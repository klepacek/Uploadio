# Platform integrations

Specifications were reviewed on 4 November 2026. Standard tests use mocked provider responses. Nothing in the test suite publishes to a real account.

## Instagram

Uploadio uses Instagram Login for professional accounts with `instagram_business_basic` and `instagram_business_content_publish`. It exchanges the short-lived token for a long-lived token and encrypts it using Fernet. A valid near-expiry token can be refreshed. Expired tokens require reconnection.

The worker creates a `REELS` or `STORIES` container using a signed R2 download URL, polls container status, then submits the container to `media_publish`. Instagram must be able to fetch that URL while it is valid. Stories omit captions; this application restricts them to business accounts. Personal accounts are rejected.

A publishing submission is recorded before the request. If the response is lost, Uploadio polls the existing container. It does not repeat an ambiguous `media_publish` request. A confirmed container publication can have no external link when the response containing the media ID was lost.

Register the exact callback URL:

```text
https://api.example.com/api/v1/oauth/instagram/callback
```

Configure the Instagram App ID and secret, app roles/test accounts, privacy policy, data deletion instructions, and the requested permissions in Meta's app dashboard. Request the required access level for accounts outside your app roles. Eligibility and final media acceptance remain Meta's decision.

Official references:

- [Business Login for Instagram](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login/)
- [Content publishing](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing/)
- [Media container reference and video specifications](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/)

Meta initially blocked the documentation reader; the current official pages were subsequently retrieved directly. The content-publishing guide carries an October 2026 revision. The selected Graph API version is configurable rather than inferred from the latest documentation.

## TikTok

Uploadio uses Login Kit and the Content Posting API. The default scope set is `user.info.basic,video.upload`. Enabling `TIKTOK_DIRECT_POST_ENABLED` adds `video.publish` to new authorization requests; existing accounts must reconnect to grant it.

For Direct Post, the composer fetches creator information, displays creator identity and duration limits, and offers privacy choices returned by TikTok. The worker checks creator information again at execution time. The creator endpoint requires `video.publish`; inbox-only accounts do not call it and remain usable with `video.upload`. Consent is required before scheduling or sending a video. Direct Post remains disabled until the operator has appropriate platform approval.

Two distinct workflows are implemented:

- Inbox upload uses `/v2/post/publish/inbox/video/init/`. `SEND_TO_USER_INBOX` becomes `draft_uploaded`; the creator must finish in TikTok. The inbox API does not apply Uploadio's caption.
- Direct Post uses `/v2/post/publish/video/init/`. A successful initialization is not treated as publication. Status is polled until completion or failure.

Media is transferred using `FILE_UPLOAD`, in sequential chunks. Provider-supplied upload URLs must use HTTPS on a TikTok API host, with no credentials or redirects. Uploadio does not accept arbitrary download URLs from users. `PULL_FROM_URL` is deliberately unused, so domain ownership verification for that transfer method is unnecessary. If URL-based transfer is added later, verify domain ownership and enforce TikTok's HTTPS, redirect and availability restrictions first.

Register the exact callback URL:

```text
https://api.example.com/api/v1/oauth/tiktok/callback
```

Unaudited Direct Post applications have restricted publishing access. A configuration flag does not grant approval or bypass provider restrictions. TikTok Stories are not supported.

Official references:

- [OAuth token lifecycle](https://developers.tiktok.com/docs/en/oauth-user-access-token-management)
- [Direct Post](https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post)
- [Inbox upload](https://developers.tiktok.com/docs/en/content-posting-api-reference-upload-video)
- [Creator information](https://developers.tiktok.com/docs/en/content-posting-api-reference-query-creator-info)
- [Media transfer](https://developers.tiktok.com/docs/en/content-posting-api-media-transfer-guide)
- [Publishing status](https://developers.tiktok.com/docs/en/content-posting-api-reference-get-video-status)
- [Content sharing guidelines](https://developers.tiktok.com/docs/en/content-sharing-guidelines)

## Live verification still required

Verify account authorization, callback URLs, granted scopes, provider revocation, token rotation, eligible Stories, R2 delivery to Meta, TikTok upload hosts, creator privacy settings, branded-content disclosure requirements, and actual publishing status transitions with approved test accounts. No provider credentials or approvals were supplied for this build.

The Direct Post interface needs a full review against TikTok's current required UX and commercial-content policies before requesting audit or enabling general access. The API supports commercial-content flags; policy combinations and localization require live audit validation.
