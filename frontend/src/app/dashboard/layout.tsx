import { requireAuth } from "@/lib/auth";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopHeader } from "@/components/layout/TopHeader";
import { MobileNav } from "@/components/layout/MobileNav";
import { Toast } from "@/components/ui/Toast";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await requireAuth();

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar role={session.role} className="hidden lg:flex" />
      <div className="flex-1 flex flex-col min-w-0">
        <TopHeader
          email={session.email}
          role={session.role}
          leadingSlot={<MobileNav role={session.role} />}
        />
        <main className="flex-1 p-4 sm:p-6">{children}</main>
      </div>
      <Toast />
    </div>
  );
}
