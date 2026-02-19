# Stripe to Deep Harbor Sync Service (ST2DH)
This service listens for subscription-related events from Stripe and updates the corresponding member records in Deep Harbor's database to ensure that membership statuses are always in sync with Stripe's subscription data.

## Stripe messages we're listening for
`customer.subscription.updated`
`customer.subscription.deleted`
`customer.subscription.created`
`customer.subscription.paused`
`customer.subscription.resumed`
`customer.updated`

