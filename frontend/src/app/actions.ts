"use server";

import { Client } from "@gradio/client";

const HF_SPACE = "Akhil-008/Olivia-Hotel-Receptionist";

export async function createBookingAction(formData: FormData) {
  try {
    const name = formData.get("name") as string;
    const email = formData.get("email") as string;
    const phone = formData.get("phone") as string;
    const arrival = formData.get("arrival") as string;
    const checkout = formData.get("checkout") as string;
    const room = formData.get("room") as string;
    const branch = formData.get("branch") as string;

    const client = await Client.connect(HF_SPACE);
    const result = await client.predict("/api_create_booking", [
      name, email, phone, arrival, checkout, room, branch
    ]);
    
    return { success: true, data: result.data };
  } catch (error: any) {
    console.error("Booking failed:", error);
    return { success: false, error: error.message };
  }
}

export async function getBookingAction(ref: string, name: string) {
  try {
    const client = await Client.connect(HF_SPACE);
    const result = await client.predict("/api_get_booking", [
      ref, name
    ]);
    
    return { success: true, data: result.data };
  } catch (error: any) {
    console.error("Failed to get booking:", error);
    return { success: false, error: error.message };
  }
}
