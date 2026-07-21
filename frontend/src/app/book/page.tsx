"use client";

import { useState, useEffect } from "react";
import { createBookingAction } from "@/app/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, Info } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const BRANCH_LABELS: Record<string, string> = {
  london: "London (Mayfair)",
  manchester: "Manchester (Deansgate)",
  edinburgh: "Edinburgh (New Town)",
};

const ROOM_LABELS: Record<string, string> = {
  standard_twin: "Standard Twin",
  deluxe_double: "Deluxe Double",
  executive_suite: "Executive Suite",
};

export default function BookPage() {
  const [loading, setLoading] = useState(false);
  const [successData, setSuccessData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [alertOpen, setAlertOpen] = useState(false);
  const [alertMode, setAlertMode] = useState<"confirm" | "error_90_days">("confirm");
  const [pendingFormData, setPendingFormData] = useState<FormData | null>(null);
  const [branch, setBranch] = useState<string>("");
  const [room, setRoom] = useState<string>("");

  const ROOM_PRICES: Record<string, Record<string, number>> = {
    london: { standard_twin: 120, deluxe_double: 180, executive_suite: 350 },
    manchester: { standard_twin: 95, deluxe_double: 155, executive_suite: 290 },
    edinburgh: { standard_twin: 105, deluxe_double: 165, executive_suite: 310 },
  };

  const [arrival, setArrival] = useState<string>("");
  const [checkout, setCheckout] = useState<string>("");

  useEffect(() => {
    if (arrival && checkout) {
      const a = new Date(arrival);
      const c = new Date(checkout);
      const diffTime = c.getTime() - a.getTime();
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      
      if (diffDays > 90) {
        setError("For bookings more than 90 days, please contact the hotel receptionist.");
      } else if (c <= a) {
        setError("Check-out date must be after check-in date.");
      } else {
        setError(null);
      }
    } else {
      setError(null);
    }
  }, [arrival, checkout]);

  const today = new Date();
  const nextWeek = new Date(today);
  nextWeek.setDate(today.getDate() + 7);
  const minCheckIn = nextWeek.toISOString().split("T")[0];
  const minCheckOut = arrival ? new Date(new Date(arrival).getTime() + 86400000).toISOString().split("T")[0] : minCheckIn;

  const getPrice = (type: string) => {
    if (!branch) return "";
    return `(£${ROOM_PRICES[branch]?.[type] || "---"})`;
  };

  async function executeBooking(formData: FormData, redirect: boolean) {
    setLoading(true);
    setError(null);
    const res = await createBookingAction(formData);
    
    const responseData = res.data as any;
    if (res.success && responseData && responseData[0]?.reference) {
      if (redirect) {
        window.location.href = `https://akhil-008-olivia-hotel-receptionist.hf.space/?pay=${responseData[0].reference}`;
      } else {
        setSuccessData(responseData[0]);
      }
    } else if (res.success && responseData && responseData[0]?.error) {
      setError(responseData[0].error);
    } else {
      setError(res.error || "An unexpected error occurred. Please try again.");
    }
    setLoading(false);
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const action = (e.nativeEvent as SubmitEvent).submitter?.getAttribute("value");
    const formData = new FormData(e.currentTarget);
    
    if (error && error.includes("90 days")) {
      setAlertMode("error_90_days");
      setAlertOpen(true);
      return;
    }
    
    if (error) return; // block submission for other inline errors

    if (action === "paynow") {
      setPendingFormData(formData);
      setAlertMode("confirm");
      setAlertOpen(true);
      return;
    }
    
    executeBooking(formData, false);
  }

  const handleConfirmPayNow = () => {
    setAlertOpen(false);
    if (pendingFormData) {
      executeBooking(pendingFormData, true);
    }
  };

  if (successData) {
    return (
      <main className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-6 text-zinc-50">
        <Card className="w-full max-w-md bg-zinc-900 border-zinc-800 text-center py-8">
          <CardHeader>
            <CheckCircle2 className="w-16 h-16 text-amber-500 mx-auto mb-4" />
            <CardTitle className="text-2xl font-serif text-zinc-100">Booking Locked!</CardTitle>
            <CardDescription className="text-zinc-400">
              Your room has been temporarily locked.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="bg-zinc-950 border border-amber-500/20 rounded-lg p-6 mb-6">
              <p className="text-sm text-zinc-400 mb-1">Your Reference Number</p>
              <p className="text-2xl font-mono text-amber-500 tracking-wider">{successData.reference}</p>
            </div>
            <p className="text-zinc-400 mb-8 text-sm">
              Please proceed to the Guest Portal to complete your payment and confirm the booking.
            </p>
            <div className="space-y-4">
              <Link href="/guest">
                <Button className="w-full bg-amber-600 hover:bg-amber-700 text-white">
                  Go to Guest Portal
                </Button>
              </Link>
              <Link href="/">
                <Button variant="ghost" className="w-full text-zinc-400 hover:text-white">
                  Return to Home
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-zinc-950 py-20 px-6 text-zinc-50 font-sans">
      <div className="max-w-2xl mx-auto">
        <Link href="/" className="inline-flex items-center gap-2 text-zinc-400 hover:text-amber-500 mb-8 transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back to Home
        </Link>
        
        <Card className="bg-zinc-900 border-zinc-800 shadow-xl">
          <CardHeader>
            <CardTitle className="text-3xl font-serif text-amber-500">Manual Booking</CardTitle>
            <CardDescription className="text-zinc-400">
              Fill in your details to secure a room at Crown & Crest. Prices vary slightly by branch.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-zinc-300">Full Name</label>
                  <Input name="name" required className="bg-zinc-950 border-zinc-800 text-white" placeholder="John Doe" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-zinc-300">Email Address</label>
                  <Input name="email" type="email" required className="bg-zinc-950 border-zinc-800 text-white" placeholder="john@example.com" />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-300">Phone Number</label>
                <Input name="phone" required className="bg-zinc-950 border-zinc-800 text-white" placeholder="+44 7700 900000" />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-zinc-300">Check-in Date</label>
                  <Input 
                    name="arrival" 
                    type="date" 
                    required 
                    min={minCheckIn}
                    value={arrival}
                    onChange={(e) => setArrival(e.target.value)}
                    className="bg-zinc-950 border-zinc-800 text-white" 
                    style={{ colorScheme: "dark" }}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-zinc-300">Check-out Date</label>
                  <Input 
                    name="checkout" 
                    type="date" 
                    required 
                    min={minCheckOut}
                    value={checkout}
                    onChange={(e) => setCheckout(e.target.value)}
                    className="bg-zinc-950 border-zinc-800 text-white" 
                    style={{ colorScheme: "dark" }}
                  />
                </div>
              </div>

              <div className="space-y-6">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-zinc-300">Branch</label>
                  <Select name="branch" value={branch} onValueChange={(val) => setBranch(val || "")}>
                    <SelectTrigger className="bg-zinc-950 border-zinc-800 text-white w-full">
                      <SelectValue placeholder="Select Branch">
                        {branch ? BRANCH_LABELS[branch] : undefined}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-950 border-zinc-800 text-white">
                      <SelectItem value="london">London (Mayfair)</SelectItem>
                      <SelectItem value="manchester">Manchester (Deansgate)</SelectItem>
                      <SelectItem value="edinburgh">Edinburgh (New Town)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-zinc-300 flex items-center justify-between">
                    Room Type
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger>
                          <Info className="w-4 h-4 text-amber-500 cursor-help" />
                        </TooltipTrigger>
                        <TooltipContent className="bg-zinc-800 border-zinc-700 text-zinc-100">
                          <p>Prices shown are base rates for the selected branch.</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </label>
                  <Select name="room" value={room} onValueChange={(val) => setRoom(val || "")} disabled={!branch}>
                    <SelectTrigger className="bg-zinc-950 border-zinc-800 text-white w-full">
                      <SelectValue placeholder={branch ? "Select Room" : "Please select a branch first"}>
                        {room && branch ? `${ROOM_LABELS[room]} ${getPrice(room)}` : undefined}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-950 border-zinc-800 text-white">
                      <SelectItem value="standard_twin">Standard Twin {getPrice("standard_twin")}</SelectItem>
                      <SelectItem value="deluxe_double">Deluxe Double {getPrice("deluxe_double")}</SelectItem>
                      <SelectItem value="executive_suite">Executive Suite {getPrice("executive_suite")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {error && (
                <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg text-red-500 text-sm">
                  {error}
                </div>
              )}

              <div className="flex flex-col sm:flex-row gap-4 mt-4">
                <Button type="submit" name="action" value="reserve" disabled={loading} className="w-full sm:w-1/2 bg-zinc-800 hover:bg-zinc-700 text-white h-12 text-lg transition-all border border-zinc-700">
                  {loading ? "Processing..." : "Fix It (Pay Later)"}
                </Button>
                <Button type="submit" name="action" value="paynow" disabled={loading} className="w-full sm:w-1/2 bg-amber-600 hover:bg-amber-700 text-white h-12 text-lg shadow-lg shadow-amber-900/20 transition-all hover:scale-[1.02]">
                  Book Now
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <AlertDialog open={alertOpen} onOpenChange={setAlertOpen}>
          <AlertDialogContent className="bg-zinc-900 border-zinc-800 text-zinc-100">
            {alertMode === "error_90_days" ? (
              <>
                <AlertDialogHeader>
                  <AlertDialogTitle className="text-red-500 text-xl">Unavailable to Book</AlertDialogTitle>
                  <AlertDialogDescription className="text-zinc-300 text-base">
                    Bookings cannot be made online for stays exceeding 90 days. Please contact the hotel receptionist directly at <span className="font-bold text-white tracking-wide">+44 20 7946 0958</span> to arrange an extended stay.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel className="bg-zinc-800 text-zinc-100 hover:bg-zinc-700 hover:text-white border-zinc-700">Okay</AlertDialogCancel>
                </AlertDialogFooter>
              </>
            ) : (
              <>
                <AlertDialogHeader>
                  <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                  <AlertDialogDescription className="text-zinc-400">
                    This will lock your room and redirect you to our Secure Payment Portal to complete your reservation. Do you want to proceed?
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel className="bg-zinc-800 text-zinc-100 hover:bg-zinc-700 hover:text-white border-zinc-700">Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={handleConfirmPayNow} className="bg-amber-600 hover:bg-amber-700 text-white">Proceed to Payment</AlertDialogAction>
                </AlertDialogFooter>
              </>
            )}
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </main>
  );
}
