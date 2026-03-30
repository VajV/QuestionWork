import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
      <div className="text-center max-w-md">
        <div className="text-8xl font-bold text-indigo-500 mb-4">404</div>
        <h2 className="text-2xl font-bold text-white mb-2">
          Страница не найдена
        </h2>
        <p className="text-gray-400 mb-6">
          Запрашиваемая страница не существует или была перемещена.
        </p>
        <Link
          href="/"
          className="inline-block px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 transition-colors font-medium"
        >
          На главную
        </Link>
      </div>
    </div>
  );
}
