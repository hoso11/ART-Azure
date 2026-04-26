"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";

interface TopHeaderProps {
  email: string;
  role: string;
  leadingSlot?: React.ReactNode;
}

export function TopHeader({ email, role, leadingSlot }: TopHeaderProps) {
  const router = useRouter();

  const handleLogout = async () => {
    await fetch("/api/v1/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    router.push("/login");
    router.refresh();
  };

  return (
    <header className="bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex items-center justify-between gap-2">
      <div className="flex items-center gap-2 min-w-0">
        {leadingSlot}
        <div className="text-sm text-gray-500 truncate">
          {role === "admin" ? "Կառավարում" : "Հաճախորդի պորտալ"}
        </div>
      </div>
      <div className="flex items-center gap-2 sm:gap-4 min-w-0">
        <span className="hidden sm:inline text-sm text-gray-700 truncate max-w-[180px] md:max-w-[260px]">
          {email}
        </span>
        <span className="text-xs px-2 py-1 rounded-full bg-brand-100 text-brand-800 font-medium whitespace-nowrap">
          {role === "admin" ? "Ադմին" : "Օգտատեր"}
        </span>
        <Button variant="ghost" size="sm" onClick={handleLogout} className="whitespace-nowrap">
          Դուրս գալ
        </Button>
      </div>
    </header>
  );
}
