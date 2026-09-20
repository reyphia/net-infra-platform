import { ApiError } from "../api/client";

export default function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null;
  const message =
    error instanceof ApiError
      ? typeof error.detail === "object"
        ? JSON.stringify(error.detail)
        : String(error.detail)
      : error instanceof Error
        ? error.message
        : String(error);
  return <div className="error-box">{message}</div>;
}
