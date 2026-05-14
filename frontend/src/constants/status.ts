export const STATUS_COLORS = ['positive', 'warning', 'negative', 'neutral'] as const;
export type StatusColor = typeof STATUS_COLORS[number];
