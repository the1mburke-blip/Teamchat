# Sale #1 Gate 1 storefront evidence

- Task [Teamchat #179](https://github.com/the1mburke-blip/Teamchat/issues/179)
- Proposed by Michael in STATUS-BREAKDOWN-BLOCKERS-01
- Executed by Codex in interactive ChatGPT Work on 10 November 2026
- [Recorded claim and preflight](https://github.com/the1mburke-blip/Teamchat/issues/179#issuecomment-6768007642)
- Final checkout readback at 2026-11-10T13:04:13.439Z
- Status VERIFYING. Independent adjudication pending. Incremental spend EUR 0.
- Evidence boundary: one responsive-layout Chromium run. Browser zoom gave a 451 CSS-pixel storefront and a 449 CSS-pixel checkout. Device emulation was blocked by browser policy. Physical handset, touch input and mobile user agent were not tested.

## UTM landing checks

Opened each URL separately and read its post-navigation address and rendered product heading, "HumanVibe Signature Tee | Unisex Streetwear Graphic Tee."

| Source | Verified URL | Rendered result |
| --- | --- | --- |
| fb | [fb](https://kivmp6-mw.myshopify.com/products/streetwear-graphic-tee?utm_source=fb&utm_medium=social&utm_campaign=sale1_launch) | Same product heading and $28.00. All three query parameters retained. |
| ig | [ig](https://kivmp6-mw.myshopify.com/products/streetwear-graphic-tee?utm_source=ig&utm_medium=social&utm_campaign=sale1_launch) | Same product heading and $28.00. All three query parameters retained. |
| direct | [direct](https://kivmp6-mw.myshopify.com/products/streetwear-graphic-tee?utm_source=direct&utm_medium=social&utm_campaign=sale1_launch) | Same product heading and $28.00. All three query parameters retained. |

URL resolution and parameter retention were observed. Analytics ingestion and attribution were outside this check.

## Reproducible checkout readback

1. Open the direct link above in a clean guest browser session at mobile width. The cart drawer initially displayed "Your cart is empty."
2. Select M and Black. The controls showed M and Black selected, quantity 1. Variant ID 47577332383798. Click Add to cart once and open the cart. It displayed one M / Black Signature Tee and an estimated total of $28.00 USD.
3. Click the standard "Check out" button. The page rendered "HumanVibe Checkout," an optional "Sign in" link, a guest contact field, Ireland as the selected country, a shipping-address prompt, and payment controls. Before entering a shipping destination the subtotal and total both read $28.00.
4. For a shipping quote only, use the [public An Post GPO address](https://www.anpost.com/Store-Locator/GPO), Dublin 1, D01 F5P2, Ireland. The test supplied this address through Shopify's checkout interface without a buyer name, email, phone or payment credential. The rendered page showed "EU Flat Rate" at $4.99 and "Order summary Total 1 item USD $32.99."
5. A separate checkout read returned status `ready_for_complete`, currency USD, and minor-unit totals of subtotal 2800, fulfillment 499, tax 0, total 3299. The Pay now control rendered. The test stopped before submitting checkout or invoking payment.

## Validation and boundaries

The final checkout read still returned "Missing a valid contact method.", "Enter a first name", "Enter a last name", and "There was a problem processing your order". The required contact and name fields were deliberately blank. The generic processing message also appeared with this unsubmitted fixture; its cause and any effect on real payment remain unverified. The zero tax line applies only to this checkout readback. No payment was submitted, no order was placed by this run, and no merchant settings or social posts were edited. The session-bound checkout URL and tokens are omitted.
