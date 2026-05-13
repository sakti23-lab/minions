export function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable;
}

export function handleChatKeyDown(e: React.KeyboardEvent, onSubmit: () => void) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    onSubmit();
  }
  if (e.key === 'Escape') {
    e.stopPropagation();
    (e.target as HTMLElement).blur();
  }
}
