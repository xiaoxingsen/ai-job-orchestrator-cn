import { validateArtifactDownload } from "../src/transport/artifact-bridge";


it("accepts only loopback artifact URLs and a complete sha256", () => {
  expect(
    validateArtifactDownload({
      name: "resume.pdf",
      path: "boss/resume.pdf",
      sha256: "a".repeat(64),
      downloadUrl: "http://127.0.0.1:8765/api/artifacts/boss/resume.pdf",
      mimeType: "application/pdf",
    }),
  ).toBe(true);
});


it("rejects remote artifact exfiltration targets", () => {
  expect(() =>
    validateArtifactDownload({
      name: "resume.pdf",
      path: "resume.pdf",
      sha256: "a".repeat(64),
      downloadUrl: "https://evil.example/resume.pdf",
      mimeType: "application/pdf",
    }),
  ).toThrow(/loopback/i);
});

