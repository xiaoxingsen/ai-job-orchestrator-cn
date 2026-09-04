import liepinSelectors from "../selectors/v1/liepin.json";
import { DomesticPlatformAdapter } from "./domestic";
import type { AttachmentBridge, SelectorBundle } from "./types";


export class LiepinAdapter extends DomesticPlatformAdapter {
  constructor(document: Document, bridge: AttachmentBridge, bundle?: SelectorBundle) {
    super(document, bridge, bundle ?? (liepinSelectors as SelectorBundle));
  }
}

