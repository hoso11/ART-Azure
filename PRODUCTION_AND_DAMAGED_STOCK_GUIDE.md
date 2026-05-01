# Production and Damaged Stock — Business Guide

A non-technical overview of how the system handles production runs, finished stock, and damaged items. Written for business owners, operations managers, and factory or warehouse users.

---

## 1. Overview

### The Production module
The Production module is where the factory plans and records the manufacturing of finished goods. An admin creates a production batch for a specific product, size, and color, with a planned quantity. The batch moves through stages — cutting, processing, quality control, packaging, warehousing, and ready for shipment — and is finally closed when the items are completed.

### The Products / Stock module
The Products module is the master catalog of what the company makes and sells. Every product has variants (combinations of size and color), and each variant carries its own stock counter that shows how many units are on hand and ready to sell. This is what salespeople and the catalog rely on to know what is available.

### Damaged / Defective stock
Not every produced item passes quality control. Some come out with stitching defects, the wrong color, tears, or other issues. The system calls these **Damaged items** (in Armenian: **Խոտան**). Damaged items are tracked in their own counter so the business can see them clearly and so they are never accidentally sold as good products.

---

## 2. Main business flow — Production for stock

This is the core flow the new feature supports.

**Example:**
1. The admin opens the Production page and creates a new batch:
   - Product: Cargo Trousers
   - Size: S
   - Color: Khaki
   - Planned quantity: 7
2. The system reserves the raw materials needed for 7 trousers and starts the batch in the "cutting" stage.
3. The batch moves through the production stages as work progresses on the factory floor.
4. When the batch is finished, the admin clicks **Complete** and is asked to enter the actual outcome:
   - **Good quantity:** 5
   - **Damaged quantity:** 2
   - **Reason** (optional): e.g., "stitching defects on 2 units"
5. The admin confirms.

**What happens next, automatically:**
- The available (sellable) stock for Cargo Trousers / S / Khaki goes up by **5**.
- The damaged stock for Cargo Trousers / S / Khaki goes up by **2**.
- The reason is saved and visible in the activity history.
- The batch is closed and locked from further changes.

---

## 3. Good stock logic

- **Good quantity** is the number of items that passed quality control.
- It is added to the normal, sellable stock for that product variant.
- These items are immediately available for orders and appear in the catalog.
- On the Products page, the good stock is shown in the regular **Մնացորդ** (Available) column, just like before.

There is no extra step needed — once the batch is completed, good items are ready to sell.

---

## 4. Damaged stock logic

- **Damaged quantity** is the number of items that did not pass quality control.
- It is added to a **separate** counter called **Damaged stock** (Խոտան).
- Damaged items are **never** added to the sellable stock and are **not** offered to customers.
- They remain visible in the system so the business can see how many defects each product has accumulated, investigate causes, and make decisions (rework, scrap, donate, etc.).
- The damaged counter is a running total: every damaged item from every completed batch adds to it. It does not reset on its own.

In short: damaged items are recorded, visible, and clearly separated — but they are not part of the inventory the business sells from.

---

## 5. Required quantity validation

When the admin enters the outcome on the completion screen, the system checks:

> **Good quantity + Damaged quantity must equal the planned quantity.**

Both numbers must be zero or positive — negative numbers are not accepted.

### Valid example

| Planned | Good | Damaged | Total | Result |
|---|---|---|---|---|
| 7 | 5 | 2 | 7 | ✅ Accepted |
| 7 | 7 | 0 | 7 | ✅ Accepted |
| 7 | 0 | 7 | 7 | ✅ Accepted |

### Invalid example

| Planned | Good | Damaged | Total | Result |
|---|---|---|---|---|
| 7 | 5 | 1 | 6 | ❌ Rejected — total is less than planned |
| 7 | 5 | 5 | 10 | ❌ Rejected — total is more than planned |
| 7 | -1 | 8 | 7 | ❌ Rejected — negative number |

### Why the system blocks incomplete totals

If the planned quantity was 7 and the admin only accounts for 6 units (5 good + 1 damaged), the missing unit is unexplained. Was it stolen? Lost in handling? Forgotten in a drawer? Counted twice somewhere else?

By requiring the totals to match exactly, the system makes sure every produced unit is recorded — either as good stock or as damaged stock. Nothing disappears silently. This protects inventory accuracy and makes losses visible the moment they happen, instead of as a surprise at the next stocktake.

---

## 6. Materials logic

- Raw materials are deducted from the warehouse **when the production batch is created**. This is unchanged from the existing flow.
- The deduction is based on the planned quantity. For 7 Cargo Trousers in size S, the system deducts the fabric, thread, buttons, etc. that 7 trousers need.
- **Damaged items still consume materials.** A trouser with a stitching defect used the same fabric as a perfect one — the fabric is gone either way.
- The system **does not** return materials to the warehouse when items are damaged. This reflects reality: the materials were used in production, even if the finished goods were rejected.
- If the business wants to recover scrap fabric or recycle damaged items, that is handled outside this system as a separate decision.

---

## 7. Products / Stock page behavior

The Products page shows each product variant on its own row, with a clear separation between sellable and damaged stock.

| Size | Color | Price | Available (Մնացորդ) | Damaged (Խոտան) |
|---|---|---|---|---|
| S | Khaki | 30 ֏ | 5 | 2 |
| M | Black | 30 ֏ | 12 | 0 |
| L | Blue | 32 ֏ | 47 | 5 |

Key points:

- **Damaged stock is always shown** in its own column, even when zero. This makes it easy for managers to spot quality issues at a glance.
- The **Available** column is unchanged in meaning — it is the stock you can actually sell.
- Damaged items are **not added** to the Available column under any circumstances.
- A non-zero damaged number is highlighted in red as a visual cue. Zero is shown in light gray.

This separation lets the business answer two different questions at the same time:
- *"How much can I ship?"* → look at Available.
- *"Where are we losing items to defects?"* → look at Damaged.

---

## 8. Reports behavior

A new report is available in the Reports section, called **Խոտանի հաշվետվություն** (Damaged Stock Report).

It shows:

- **Ընդհանուր խոտան** — the total number of damaged items across the entire catalog.
- **Ապրանքների քանակ** — how many distinct products have at least one damaged unit.
- **Տարբերակների քանակ** — how many product variants (size/color combinations) have damaged units.
- A detailed table listing every product variant that has damaged stock, with the product name, size, color, and damaged quantity.

The report can be viewed on screen and exported as a CSV file for use in spreadsheets.

Important reporting rules:

- Damaged stock is **never** counted as sellable inventory in any report.
- Existing reports (Orders, Sales, Inventory, Material Consumption, Production, Low Stock, Customer Discounts) continue to work exactly as before. They were not changed.
- Variants with zero damaged stock are not listed in the damaged report — only variants where the business actually has a defect history appear.

This gives managers a clear, at-a-glance view of quality losses without polluting the regular stock and sales reports.

---

## 9. What is NOT included in Phase 1

This release covers **production-for-stock** batches only.

A production-for-stock batch is when the factory produces items to replenish general inventory, not against a specific customer order. The damaged-stock feature applies to these batches.

The following is **not yet implemented** and will be addressed in Phase 2:

- **Damaged tracking on customer-order production.** When the factory produces items specifically to fulfill a customer order, and some of those items come out damaged, the current system does not yet record the damaged portion against the order. The order's production workflow remains unchanged.
- **Customer-facing communication** about partial fulfillment caused by damaged items.
- **Automatic re-production** of missing units lost to defects in customer orders.

For now, if damage occurs during customer-order production, the operations team should handle it manually (for example, by creating a new internal production batch to replace the missing units) until Phase 2 is delivered.

---

## 10. Phase 2 — Order-based damaged production (planned)

When a customer orders 10 Cargo Trousers and the factory produces 8 good and 2 damaged, the business needs to decide what happens to the order. Three reasonable approaches exist; the right one depends on the company's policy and customer relationships.

| Option | Description | Best when |
|---|---|---|
| **A. Re-produce automatically** | The system creates a small follow-up production run to replace the 2 damaged units, so the customer eventually receives all 10 good items. The order stays open until the replacement batch is done. | Service-level commitments are strict and the company prefers to absorb the delay rather than disappoint the customer. |
| **B. Mark order as partially fulfilled** | The order is flagged as partially complete. An operations manager reviews it and chooses: re-produce, ship the good portion now and produce the rest later, or contact the customer. | The company wants a human in the loop for every short-fulfillment decision. |
| **C. Ship-short with customer confirmation** | The customer is contacted, told that 8 of 10 are available, and asked whether they want to receive 8 now (with a credit or refund for the missing 2) or wait for a re-run. | Customers value speed over completeness, and the company has good direct communication channels. |

The product owner needs to choose one of these (or a clear hybrid) **before** Phase 2 begins. Until that decision is made, the order-based damaged feature stays paused.

---

## 11. Business benefits

The Phase 1 release delivers concrete operational improvements:

- **More accurate stock.** Every produced unit is accounted for as either good or damaged. The "where did the missing trousers go?" question disappears.
- **Clear separation between sellable and damaged items.** Salespeople, the catalog, and order fulfillment never accidentally promise a damaged unit to a customer.
- **Better quality-control visibility.** Managers can see at a glance which products and which variants are accumulating defects, and respond — investigate the supplier, retrain the line, change a pattern, etc.
- **Better reporting for factory losses.** The damaged report turns "we had a bad week" into a number the business can track over time and report to leadership.
- **Less manual tracking outside the system.** Notebooks, side-spreadsheets, and verbal handovers between shift managers about defects are no longer needed for stock-based production. The system is the single source of truth.

---

## 12. Simple examples

Three short examples showing the system in action.

### Example 1 — All items good

A batch of **10 Polo Shirts (M / White)** is produced. Every item passes QC.

- Planned: 10
- Good: 10
- Damaged: 0
- **Result:** Available stock for Polo Shirt M / White goes up by 10. Damaged stock is unchanged.

### Example 2 — All items damaged

A batch of **5 Summer Dresses (L / Linen)** is produced, but the wrong fabric color was used. None of the 5 can be sold as catalog items.

- Planned: 5
- Good: 0
- Damaged: 5
- Reason: "Wrong fabric color — does not match catalog spec"
- **Result:** Available stock for Summer Dress L / Linen is unchanged. Damaged stock goes up by 5. Materials are not refunded — they were consumed.

### Example 3 — Partially good, partially damaged

A batch of **7 Cargo Trousers (S / Khaki)** is produced. 5 pass QC; 2 have stitching defects.

- Planned: 7
- Good: 5
- Damaged: 2
- Reason: "Stitching defects on 2 units"
- **Result:** Available stock for Cargo Trousers S / Khaki goes up by 5. Damaged stock goes up by 2. The batch is closed.

---

## Summary

Phase 1 introduces a simple, strict rule for finishing a production batch: **the admin must say exactly how many items came out good and how many came out damaged, and the two numbers must add up to the planned quantity**. Good items go to sellable stock and behave like before. Damaged items go to a separate damaged counter, are visible on the Products page and in a dedicated report, and are never confused with stock available for sale. Materials are consumed regardless of outcome, reflecting reality.

The result: nothing disappears from the books, salespeople never sell something the warehouse cannot deliver, and managers gain a real, measurable view of quality losses. Order-based damaged tracking — for items damaged while producing against a specific customer order — is intentionally left for Phase 2, pending a business decision on how short-fulfilled orders should be handled.
