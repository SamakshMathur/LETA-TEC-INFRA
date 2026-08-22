// Single entry point for all components.
// Import from here or directly from the subfolder barrel — both work.
//
// NOTE: ui/Button is omitted here because common/Button also exports a name
// "Button". Import ui/Button explicitly: import { Button } from './ui'

export * from './auth';
export * from './common';
export * from './dashboard';
export * from './documents';
export * from './effects';
export * from './landing';
export * from './layout';
export * from './leta';
export * from './templates';
export * from './typography';
// ui — skip Button to avoid name clash with common/Button
export { MagneticButton, SelectSwitcher, SoftAurora } from './ui';
