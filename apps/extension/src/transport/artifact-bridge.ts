import type { ArtifactRef, AttachmentBridge } from "../adapters/types";


const ALLOWED_MIME_TYPES = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]);
const MAX_ARTIFACT_BYTES = 10 * 1024 * 1024;


export function validateArtifactDownload(artifact: ArtifactRef): true {
  const url = new URL(artifact.downloadUrl);
  if (url.protocol !== "http:" || !["127.0.0.1", "localhost", "::1"].includes(url.hostname)) {
    throw new Error("artifact downloads must use an HTTP loopback URL");
  }
  if (!/^[a-f\d]{64}$/i.test(artifact.sha256)) throw new Error("artifact SHA-256 is invalid");
  if (!ALLOWED_MIME_TYPES.has(artifact.mimeType)) throw new Error("artifact MIME type is not allowed");
  if (!artifact.name || /[\\/]/.test(artifact.name)) throw new Error("artifact filename is invalid");
  return true;
}


async function sha256Hex(data: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}


export class LocalArtifactBridge implements AttachmentBridge {
  async attach(input: HTMLInputElement, artifact: ArtifactRef): Promise<boolean> {
    try {
      validateArtifactDownload(artifact);
      const response = await fetch(artifact.downloadUrl, {
        cache: "no-store",
        credentials: "omit",
        redirect: "error",
      });
      if (!response.ok) return false;
      const declaredLength = Number(response.headers.get("content-length") ?? 0);
      if (declaredLength > MAX_ARTIFACT_BYTES) return false;
      const data = await response.arrayBuffer();
      if (data.byteLength > MAX_ARTIFACT_BYTES) return false;
      if ((await sha256Hex(data)) !== artifact.sha256.toLowerCase()) return false;

      const file = new File([data], artifact.name, { type: artifact.mimeType });
      const transfer = new DataTransfer();
      transfer.items.add(file);
      input.files = transfer.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
      return input.files?.length === 1;
    } catch {
      return false;
    }
  }
}

