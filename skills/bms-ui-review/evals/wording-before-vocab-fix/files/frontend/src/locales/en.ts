/** English: the source of truth. Every other language defines the same keys. */
export const en = {
    "nav.orders": "Orders",
    "nav.products": "Products",
    "nav.customers": "Customers",
    "nav.settings": "Settings",
    "orders.title": "Orders",
    "orders.empty": "No orders yet",
    "orders.search": "Search orders",
    "orders.cancel": "Cancel",
    "orders.discard": "Discard",
    "orders.delete": "Delete",
    "orders.remove": "Remove line",
    "orders.addLine": "Add line",
    "orders.addNote": "Add a note",
    "products.add": "Add a product",
    "products.addImage": "Add image",
    "products.save": "Save",
    "products.saved": "Saved.",
    "customers.saved": "Saved",
    "customers.addTag": "Add a tag",
    "customers.remove": "Remove",
    "customers.delete": "Delete customer",
    "settings.cancel": "Cancel",
    "settings.discard": "Discard changes",
    "settings.title": "Settings",
    "settings.language": "Language",
    "common.close": "Close",
    "common.loading": "Loading…",
} as const;

export type MessageKey = keyof typeof en;
export type Messages = Record<MessageKey, string>;
