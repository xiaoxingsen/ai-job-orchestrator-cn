import bossSelectors from "../selectors/v1/boss.json";
import { DomesticPlatformAdapter } from "./domestic";
import type { AttachmentBridge, SelectorBundle } from "./types";


export class BossAdapter extends DomesticPlatformAdapter {
  constructor(document: Document, bridge: AttachmentBridge, bundle?: SelectorBundle) {
    super(document, bridge, bundle ?? (bossSelectors as SelectorBundle));
  }
}

