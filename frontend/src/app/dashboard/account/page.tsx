import { requireAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

export default async function AccountPage() {
  const session = await requireAuth();

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Իմ հաշիվ</h1>

      <Card className="max-w-lg">
        <CardHeader><h3 className="font-semibold">Հաշիվի տեղեկություն</h3></CardHeader>
        <CardContent>
          <dl className="space-y-4">
            <div>
              <dt className="text-xs text-gray-500">Email</dt>
              <dd className="text-sm font-medium">{session.email}</dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500">Դեր</dt>
              <dd>
                <Badge className={session.role === "admin" ? "bg-purple-100 text-purple-800" : "bg-blue-100 text-blue-800"}>
                  {session.role === "admin" ? "Կառավարիչ" : "Հաճախորդ"}
                </Badge>
              </dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500">Հաշիվի ID</dt>
              <dd className="text-sm">{session.user_id}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
