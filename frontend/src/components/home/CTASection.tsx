import Link from "next/link";

export function CTASection() {
  return (
    <section id="contact" className="py-20 bg-brand-800">
      <div className="max-w-4xl mx-auto px-6 text-center">
        <h2 className="text-3xl font-bold text-white mb-4">
          Պատրա՞ստ եք սկսել ձեր հաջորդ արտադրական պատվերը
        </h2>
        <p className="text-brand-200 text-lg mb-8 max-w-2xl mx-auto">
          Մուտք գործեք ձեր հաճախորդի էջ՝ մեր կատալոգը դիտելու, պատվերներ ձևակերպելու և արտադրության ընթացքը իրական ժամանակում հետևելու համար։ Եթե նոր եք ART Արտադրությունում, կապ հաստատեք մեր վաճառքի թիմի հետ՝ ձեր հաշիվը ակտիվացնելու համար։
        </p>
        <div className="flex flex-wrap justify-center gap-4">
          <Link
            href="/login"
            className="px-8 py-3.5 bg-white text-brand-900 font-semibold rounded-lg hover:bg-brand-50 transition-colors"
          >
            Մուտք հաճախորդների համար
          </Link>
          <a
            href="mailto:sales@art-manufacturing.com"
            className="px-8 py-3.5 border-2 border-brand-400 text-white font-semibold rounded-lg hover:bg-brand-700 transition-colors"
          >
            Կապ վաճառքի բաժնի հետ
          </a>
        </div>
      </div>
    </section>
  );
}
