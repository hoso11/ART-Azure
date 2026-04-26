import { Product } from "@/types";
import { formatCurrency } from "@/lib/utils";

interface FeaturedProductsProps {
  products: Product[];
}

function ProductPlaceholder() {
  return (
    <svg className="h-16 w-16 text-brand-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
    </svg>
  );
}

function getProductPrimaryImage(product: Product): string | null {
  const primary = product.images?.find((img) => img.is_primary);
  if (primary?.url) return primary.url;
  const first = product.images?.[0];
  if (first?.url) return first.url;
  return null;
}

// Translation maps for product data coming from the API
const categoryNames: Record<string, string> = {
  Trousers: "Տաբատներ",
  Shirts: "Շապիկներ",
  Jackets: "Բաճկոններ",
  Uniforms: "Համազգեստներ",
  Dresses: "Զգեստներ",
};

const productNames: Record<string, string> = {
  "Cargo Trousers": "Կարգո տաբատ",
  "Formal Dress Shirt": "Պաշտոնական վերնաշապիկ",
  "Denim Work Jacket": "Ջինսե աշխատանքային բաճկոն",
  "Corporate Polo Uniform": "Կորպորատիվ պոլո համազգեստ",
  "Summer Linen Dress": "Ամառային կտավատի զգեստ",
  "Wool Blend Blazer": "Բրդյա խառնուրդով բլեյզեր",
  "Slim Fit Chinos": "Նեղ ձևվածքի չինոս",
  "Classic Oxford Shirt": "Դասական օքսֆորդ վերնաշապիկ",
};

const productDescriptions: Record<string, string> = {
  "Multi-pocket cargo trousers": "Բազմագրպան կարգո տաբատ",
  "Tailored formal dress shirt": "Կարված պաշտոնական վերնաշապիկ",
  "Heavy-duty denim work jacket": "Ամուր և գործնական ջինսե աշխատանքային բաճկոն",
  "Branded corporate polo": "Բրենդավորված կորպորատիվ պոլո",
  "Light summer linen dress": "Թեթև ամառային կտավատի զգեստ",
  "Tailored wool blend blazer": "Կարված բրդյա խառնուրդով բլեյզեր",
  "Modern slim fit chinos": "Պամանակակից նեղ ձևվածքի չինոս",
  "Timeless oxford button-down shirt": "Դասական օքսֆորդ ոճի կոճկվող վերնաշապիկ",
};

function t(map: Record<string, string>, key: string | undefined | null): string {
  if (!key) return "";
  return map[key] || key;
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
            const imageUrl = getProductPrimaryImage(product);
            return (
              <div
                key={product.id}
                className="bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow"
              >
                <div className="h-48 bg-brand-50 flex items-center justify-center">
                  {imageUrl ? (
                    <img
                      src={imageUrl}
                      alt={t(productNames, product.name)}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <ProductPlaceholder />
                  )}
                </div>
                <div className="p-4">
                  <p className="text-xs text-brand-500 font-medium uppercase">{t(categoryNames, product.category?.name)}</p>
                  <h3 className="font-semibold text-gray-900 mt-1">{t(productNames, product.name)}</h3>
                  <p className="text-sm text-gray-500 mt-1 line-clamp-2">{t(productDescriptions, product.description)}</p>
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
