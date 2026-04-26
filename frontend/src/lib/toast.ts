export type ToastType = "success" | "error";

export interface ToastDetail {
  message: string;
  type: ToastType;
}

export function showToast(message: string, type: ToastType = "success") {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent<ToastDetail>("app:toast", { detail: { message, type } })
  );
}
