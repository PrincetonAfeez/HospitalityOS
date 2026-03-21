#Project: "Digital Front Desk"

import random
import digitalpos # Import your 2nd script
# Import the custom validation module
from validator import get_name, get_email, get_int, get_date, get_time, get_yes_no

def main():
    """
    The main engine of the script. 
    Coordinates the reservation intake and the guest arrival process.
    """
    print("\n--- Part A: Reservation InTake ---\n")
    
    # Collect all validated reservation details
    first, last, adults, kids, allergies = get_resy_details()
    
    # Use those details to process the guest's physical arrival
    handle_arrival(first, last, adults, kids, allergies)

def get_resy_details():
    """
    Collects and validates all guest information for a new booking.
    """
    print("--- MyRestaurant Reservation System ---")
    
    # Basic Guest Information
    first_name = get_name("First Name: ")
    last_name = get_name("Last Name: ")
    email = get_email("Email Address: ")
    
    # 10-digit mobile number, must not be empty/zero
    phone = get_int("Mobile (10 digits): ", exact_len=10)
    
    # Party Size: Adults must be at least 1, Children can be 0
    adults = get_int("Number of Adults: ", min_val=1)
    children = get_int("Number of Children: ", allow_zero=True)
    
    # Date & Time: Using our 'Natural Language' and 'Business Hour' logic
    date = get_date("Reservation Date (e.g., Oct 12th): ")
    # Restaurant opens at 11am (11), last booking at 9pm (21)
    resy_time = get_time("Reservation Time (e.g., 7pm or 19:00): ", start_hour=11, end_hour=21)
    
    # Allergy logic: Only asks for items if the guest says 'yes'
    allergies = []
    if get_yes_no("Are there any food allergies for this party? (y/n): "):
        print("Enter allergies one by one (type 'done' when finished):")
        while True:
            item = input("> ").strip().title()
            if item.lower() == "done":
                break
            if item:
                allergies.append(item)

    # Confirmation summary for the guest
    print(f"\n--- Reservation Confirmed ---")
    print(f"Guest: {first_name} {last_name} | Date: {date} at {resy_time}")
    
    return first_name, last_name, adults, children, allergies

def handle_arrival(first_name, last_name, adults, children, allergies):
    """
    Handles the arrival of the guest and table assignment.
    """
    print(f"\n--- Part B: Guest Arrival ---")
    print(f"Welcome back, {first_name} {last_name}!")
    
    # Update party size: uses get_yes_no to simplify the choice logic
    if get_yes_no("Is the party size still the same? (y/n): "):
        total_guests = adults + children
    else:
        new_adults = get_int("Updated adult count: ", min_val=1)
        new_kids = get_int("Updated children count: ", allow_zero=True)
        total_guests = new_adults + new_kids
    
    # Kitchen notification for allergies
    if allergies:
        print(f"\n*** KITCHEN ALERT: {', '.join(allergies)} ***")

    # Table assignment logic
    if get_yes_no("Do you have a specific table preference? (y/n): "):
        table_num = get_int("Enter Table Number (1-99): ", min_val=1, max_val=99)
    else:
        # Assign a random table if no preference
        table_num = random.randint(1, 99)
        print(f"No problem, we have assigned you Table {table_num}.")

    print(f"\nEnjoy your meal! Table {table_num} is ready for {total_guests} guests.")

    # Pass the validated table number directly to the POS
    digitalpos.run_pos(table_num)

if __name__ == "__main__":
    main()