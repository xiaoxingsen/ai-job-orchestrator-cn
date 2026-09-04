import zhilianSelectors from "../selectors/v1/zhilian.json";
import { DomesticPlatformAdapter } from "./domestic";
import type { AttachmentBridge, SelectorBundle } from "./types";


export class ZhilianAdapter extends DomesticPlatformAdapter {
  constructor(document: Document, bridge: AttachmentBridge, bundle?: SelectorBundle) {
    super(document, bridge, bundle ?? (zhilianSelectors as SelectorBundle));
  }
}

