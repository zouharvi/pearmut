import { notify } from "./utils"
import $ from 'jquery';

let searchParams = new URLSearchParams(window.location.search)

export async function get_next_item<T>(): Promise<T | null> {
  /* Fetch the next item for the user from the server. */
  let user_id = searchParams.get("user_id");
  let campaign_id = searchParams.get("campaign_id");

  let delay = 1
  while (true) {
    try {
      return await new Promise<T>((resolve, reject) => {
        $.ajax({
          url: `get-next-item`,
          method: "POST",
          data: JSON.stringify({ "campaign_id": campaign_id, "user_id": user_id }),
          contentType: "application/json",
          dataType: "json",
          success: (x) => resolve(x),
          error: (XMLHttpRequest, textStatus, errorThrown) => {
            console.error("Error fetching data:", textStatus, errorThrown);
            if (XMLHttpRequest.status === 0) {
              reject("Can't reach server.");
              return;
            }
            reject(`${XMLHttpRequest.status}: ${XMLHttpRequest.responseText}`);
          },
        });
      });
    } catch (e) {
      console.log("Error in try-catch:", e);
      notify(`Error fetching item. <br><br> ${e} <br><br> Retrying in ${delay} seconds...`);
    }
    // wait for 5 seconds
    await new Promise(resolve => setTimeout(resolve, delay * 1000));
    delay *= 2
    // if more than 1 minute, give up
    if (delay > 60) return null
  }
}


export async function log_response(payload: any, item_i: number | null): Promise<boolean | null> {
  /* Log the user's response to the server. */
  let user_id = searchParams.get("user_id");
  let campaign_id = searchParams.get("campaign_id");

  let delay = 1
  while (true) {
    try {
      await new Promise<void>((resolve, reject) => {
        $.ajax({
          url: `log-response`,
          method: "POST",
          data: JSON.stringify({ "campaign_id": campaign_id, "user_id": user_id, "payload": payload, "item_i": item_i }),
          contentType: "application/json",
          dataType: "json",
          success: (x) => resolve(),
          error: (XMLHttpRequest, textStatus, errorThrown) => {
            console.error("Error storing data:", textStatus, errorThrown);
            if (XMLHttpRequest.status === 0) {
              reject("Can't reach server.");
              return;
            }
            reject(`${XMLHttpRequest.status}: ${XMLHttpRequest.responseText}`);
          },
        });
      });
      return true;
    } catch (e) {
      console.log("Error in try-catch:", e);
      notify(`Error storing item. <br><br> ${e} <br><br> Retrying in ${delay} seconds...`);
    }
    // wait for 5 seconds
    await new Promise(resolve => setTimeout(resolve, delay * 1000));
    delay *= 2
    // if more than 2 minutes, give up
    if (delay > 120) return null
  }
}

export async function get_i_item<T>(item_i: number | string): Promise<T | null> {
  /* Fetch a specific item by index for the user from the server. */
  let user_id = searchParams.get("user_id");
  let campaign_id = searchParams.get("campaign_id");

  let delay = 1
  while (true) {
    try {
      return await new Promise<T>((resolve, reject) => {
        $.ajax({
          url: `get-i-item`,
          method: "POST",
          data: JSON.stringify({ "campaign_id": campaign_id, "user_id": user_id, "item_i": item_i }),
          contentType: "application/json",
          dataType: "json",
          success: (x) => resolve(x),
          error: (XMLHttpRequest, textStatus, errorThrown) => {
            console.error("Error fetching data:", textStatus, errorThrown);
            if (XMLHttpRequest.status === 0) {
              reject("Can't reach server.");
              return;
            }
            reject(`${XMLHttpRequest.status}: ${XMLHttpRequest.responseText}`);
          },
        });
      });
    } catch (e) {
      console.log("Error in try-catch:", e);
      notify(`Error fetching item. <br><br> ${e} <br><br> Retrying in ${delay} seconds...`);
    }
    // wait for 5 seconds
    await new Promise(resolve => setTimeout(resolve, delay * 1000));
    delay *= 2
    // if more than 2 minutes, give up
    if (delay > 120) return null
  }
}
