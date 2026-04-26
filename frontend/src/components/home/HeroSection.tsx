import Link from "next/link";

export function HeroSection() {
  return (
    <section className="relative bg-brand-900 text-white overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-brand-900 via-brand-800 to-brand-700" />
      <div className="relative max-w-7xl mx-auto px-6 py-24 md:py-32">
        <div className="max-w-3xl">
          <p className="text-brand-300 text-sm font-semibold tracking-widest uppercase mb-4">
            Բարձր ճշգրտության արտադրություն՝ 2003 թվականից
          </p>
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold leading-tight mb-6">
            Որտեղ որակը միանում է
            <br />
            <span className="text-brand-300">վարպետությանը</span>
          </h1>
          <p className="text-lg text-brand-200 leading-relaxed mb-8 max-w-2xl">
            Մենք արտադրում ենք բարձրորակ հագուստ աշխարհի տարբեր բրենդների համար։ Գաղափարից մինչև վերջնական առաքում՝ մեր ամբողջական արտադրական համակարգը ապահովում է, որ յուրաքանչյուր հագուստ համապատասխանի որակի և ճշգրտության ամենաբարձր չափանիշներին։
          </p>
          <div className="flex flex-wrap gap-4">
            <Link
              href="/login"
              className="px-8 py-3.5 bg-white text-brand-900 font-semibold rounded-lg hover:bg-brand-50 transition-colors"
            >
              Հաճախորդի էջ
            </Link>
            <Link
              href="#products"
              className="px-8 py-3.5 border-2 border-brand-400 text-white font-semibold rounded-lg hover:bg-brand-800 transition-colors"
            >
              Դիտել ապրանքները
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
