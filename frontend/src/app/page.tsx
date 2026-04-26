import { PublicNav } from "@/components/layout/PublicNav";
import { Footer } from "@/components/layout/Footer";
import { HeroSection } from "@/components/home/HeroSection";
import { FeaturedProducts } from "@/components/home/FeaturedProducts";
import { CategoriesOverview } from "@/components/home/CategoriesOverview";
import { WhyChooseUs } from "@/components/home/WhyChooseUs";
import { CTASection } from "@/components/home/CTASection";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL || "http://backend:8000";

async function getPublicProducts() {
  try {
    const res = await fetch(`${INTERNAL_API_URL}/api/v1/products/public?limit=8`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.items || [];
  } catch {
    return [];
  }
}

async function getCategories() {
  try {
    const res = await fetch(`${INTERNAL_API_URL}/api/v1/categories`, {
      cache: "no-store",
      headers: { Cookie: "" },
    });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export default async function HomePage() {
  const [products, categories] = await Promise.all([
    getPublicProducts(),
    getCategories(),
  ]);

  return (
    <div className="min-h-screen">
      <PublicNav />
      <HeroSection />
      <FeaturedProducts products={products} />
      <CategoriesOverview categories={categories} />
      <WhyChooseUs />
      <CTASection />
      <Footer />
    </div>
  );
}
