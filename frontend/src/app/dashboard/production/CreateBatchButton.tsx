"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { CreateBatchModal } from "./CreateBatchModal";

export function CreateBatchButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>Ստեղծել արտադրություն</Button>
      <CreateBatchModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}
