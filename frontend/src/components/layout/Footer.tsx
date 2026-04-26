export function Footer() {
  return (
    <footer className="bg-brand-900 text-brand-200">
      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          <div>
            <h3 className="text-white font-bold text-lg mb-3">ART Արտադրություն</h3>
            <p className="text-sm leading-relaxed">
              Բարձրակարգ հագուստի արտադրություն՝ ավելի քան 20 տարվա փորձով։ Դիզայնից մինչև առաքում՝ մենք որակ ենք ապահովում յուրաքանչյուր կարի մեջ։
            </p>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-3">Ծառայություններ</h4>
            <ul className="space-y-2 text-sm">
              <li>Պատվերով արտադրություն</li>
              <li>Արտադրություն մասնավոր պիտակով</li>
              <li>Ձևվածքների մշակում</li>
              <li>Որակի ապահովում</li>
            </ul>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-3">Կապ</h4>
            <ul className="space-y-2 text-sm">
              <li>info@art-manufacturing.com</li>
              <li>+1 (555) 123-4567</li>
              <li>123 Industrial Blvd</li>
              <li>Manufacturing District, NY 10001</li>
            </ul>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-3">Աշխատանքային ժամեր</h4>
            <ul className="space-y-2 text-sm">
              <li>Երկուշաբթի - Ուրբաթ: 08:00 - 18:00</li>
              <li>Շաբաթ: 09:00 - 13:00</li>
              <li>Կիրակի: Փակ է</li>
            </ul>
          </div>
        </div>

        <div className="mt-10 pt-8 border-t border-brand-700 text-center text-sm text-brand-400">
          &copy; {new Date().getFullYear()} ART Արտադրություն։ Բոլոր իրավունքները պաշտպանված են։
        </div>
      </div>
    </footer>
  );
}
