import { useToast, type ToastType } from '../store/toast'

const colors: Record<ToastType, string> = {
  success: 'bg-emerald-500',
  error: 'bg-red-600',
  info: 'bg-amber-600',
  warning: 'bg-amber-600',
}

export function ToastHost() {
  const { toasts } = useToast()
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`rounded-lg px-4 py-3 text-sm font-medium ${t.type === 'error' ? 'text-white' : 'text-black'} shadow-lg ${colors[t.type]}`}
        >
          {t.message}
        </div>
      ))}
    </div>
  )
}