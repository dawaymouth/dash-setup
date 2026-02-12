/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_STATIC_DATA?: string;
  readonly VITE_EXTERNAL_SHARING?: string;
  readonly VITE_DASHBOARD_PASSWORD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
