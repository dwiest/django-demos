# Shipping and tracking

Run Django migrations before using shipping management (store migration 0011).

In Store settings, configure the domestic standard shipping charge, optional free
shipping threshold, and processing estimate. The threshold uses merchandise value
after discounts. Checkout remains US-only and simulated; no postage or payment is
purchased. Existing orders retain their original shipping charge and method.

Open an order in Manage orders and choose Create shipment. Enter carrier, tracking,
optional HTTPS tracking link, dispatch date, and the quantities in that package.
Choose whether you or a supplier shipped it. Supplier deliveries to your own shop
are inventory receipts, not customer shipments. Stock allocations must be sent by
you; supplier shipments can contain the print-on-demand allocation.

Save with Notify customer checked to send an email using store email artwork and
copy. Leave it unchecked to record a shipment quietly. Order history allows a first
send or retry; Edit tracking allows corrections without email, or an explicit resend.
Email timestamps mean the configured backend accepted the message, not delivery to
the recipient. Email delivery remains synchronous after database commit, as with
existing order notifications; there is no background retry worker.

Shipments consume reserved local stock only for included quantities, and repeated
submission of the same shipment form does not create another package. Partial
shipments show as Partially shipped; the order becomes Fulfilled after all items
ship. Orders with shipments lock item, address, and status edits to protect shipment
and inventory history. Customer email corrections and messages remain available.
Historical fulfilled orders keep their legacy tracking; no shipment is fabricated.

Carrier delivery scans, postage labels, live rates, international shipping, supplier
APIs, shipment reversal, and cancellation of the remainder of a partial order are
outside this initial implementation.
