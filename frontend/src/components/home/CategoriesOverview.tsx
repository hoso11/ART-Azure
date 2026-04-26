import { ProductCategory } from "@/types";

interface CategoriesOverviewProps {
  categories: ProductCategory[];
}

const categoryIcons: Record<string, string> = {
  Shirts: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
  Trousers: "M16 4v16m-8-16v16m-4-8h16",
  Jackets: "M15 5v2m0 4v2m0 4v2M5 3h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2z",
  Dresses: "M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z",
  Uniforms: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2",
};

export function CategoriesOverview({ categories }: CategoriesOverviewProps) {
  if (categories.length === 0) return null;

  return (
    <section className="py-20 bg-gray-50">
      <div className="max-w-7xl mx-auto px-6">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold text-gray-900 mb-3">Product Categories</h2>
          <p className="text-gray-600 max-w-2xl mx-auto">
            We specialize in manufacturing across multiple garment categories,
            each with dedicated production lines and quality standards.
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6">
          {categories.map((cat) => (
            <div
              key={cat.id}
              className="bg-white rounded-lg p-6 text-center hover:shadow-md transition-shadow border border-gray-100"
            >
              <div className="mx-auto w-12 h-12 bg-brand-50 rounded-full flex items-center justify-center mb-4">
                <svg className="h-6 w-6 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d={categoryIcons[cat.name] || categoryIcons["Shirts"]} />
                </svg>
              </div>
              <h3 className="font-semibold text-gray-900">{cat.name}</h3>
              {cat.description && (
                <p className="text-sm text-gray-500 mt-1">{cat.description}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
