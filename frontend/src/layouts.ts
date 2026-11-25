export type Layout = 'standard' | 'compact' | 'focus';
export type Widget = 'tasks' | 'calendar' | 'activity' | 'quick_actions' | 'reports' | 'notifications';
export const allWidgets: Widget[] = ['tasks','calendar','activity','quick_actions','reports','notifications'];
export const orders: Record<Layout, Widget[]> = {
  standard: ['tasks','calendar','activity','quick_actions','reports','notifications'],
  compact: ['quick_actions','tasks','notifications','calendar','reports','activity'],
  focus: ['tasks','reports','calendar','quick_actions','activity','notifications']
};
export const labels: Record<Widget, string> = {tasks:'Завдання',calendar:'Календар',activity:'Активність',quick_actions:'Швидкі дії',reports:'Звіти',notifications:'Сповіщення'};
