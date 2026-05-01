import { Product } from "@/types";
import { formatCurrency } from "@/lib/utils";
import { ProductCardImage } from "@/components/products/ProductCardImage";

interface FeaturedProductsProps {
  products: Product[];
}

export function FeaturedProducts({ products }: FeaturedProductsProps) {
  if (products.length === 0) return null;

  return (
    <section id="products" className="py-20 bg-white">
      <div className="max-w-7xl mx-auto px-6">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold text-gray-900 mb-3">Մեր ապրանքները</h2>
          <p className="text-gray-600 max-w-2xl mx-auto">
            Ծանոթացեք մեր արտադրած հագուստի կատալոգին՝ կորպորատիվ համազգեստներից մինչև բարձրակարգ նորաձևության մոդելներ։ Եուրաքանչյուր ապրանք կարող է հարմարեցվել ձեր պահանջներին։
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {products.map((product) => {
            const minPrice = product.variants.length
              ? Math.min(...product.variants.map((v) => v.price))
              : 0;
            return (
              <div
                key={product.id}
                className="bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow"
              >
                <ProductCardImage
                  images={product.images || []}
                  productName={product.name}
                />
                <div className="p-4">
                  <p className="text-xs text-brand-500 font-medium uppercase">{product.category?.name}</p>
                  <h3 className="font-semibold text-gray-900 mt-1">{product.name}</h3>
                  <p className="text-sm text-gray-500 mt-1 line-clamp-2">{product.description}</p>
                  <div className="mt-3 flex items-center justify-between">
                    <span className="text-brand-800 font-semibold">
                      {minPrice > 0 ? `Սկսած ${formatCurrency(minPrice)}-ից` : "Կապվեք գնագոյացման համար"}
                    </span>
                    <span className="text-xs text-gray-400">{product.sku}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
