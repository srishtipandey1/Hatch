from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        agent_id = "3aca252d-ac6f-4c72-9889-0bbfc6976d41"
        print(f"Navigating to http://127.0.0.1:5174/a/{agent_id} ...")
        page.goto(f"http://127.0.0.1:5174/a/{agent_id}", timeout=20000)

        # Verify page loaded
        page.wait_for_selector(".spec", timeout=15000)
        spec_title = page.locator("#spec-title").inner_text()
        print(f"Spec loaded: {spec_title}")

        # Verify report table loaded
        page.wait_for_selector(".report", timeout=15000)
        report_title = page.locator("#report-title").inner_text()
        print(f"Report loaded: {report_title}")
        rows = page.locator("table tbody tr").count()
        print(f"Verdicts table row count: {rows}")
        assert rows == 7

        # Verify Step 4: Talk Panel
        talk_section = page.locator("#talk-section")
        assert talk_section.is_visible()
        print("Talk section is visible on single page.")

        # Test Order Lookup
        input_box = page.locator(".text-turn input")
        input_box.fill("Mera order ORD-1004 kahan hai?")
        page.locator(".text-turn button").click()
        print("Sent order lookup turn...")

        page.wait_for_function("document.querySelectorAll('.bubble').length >= 3", timeout=30000)
        bubbles = page.locator(".bubble p").all_inner_texts()
        reply1 = bubbles[-1]
        print(f"Agent order reply: {reply1}")
        assert "ORD-1004" in reply1 or "delay" in reply1.lower()

        # Test Angry Caller / Human Handoff
        input_box.fill("Mujhe kisi manager se baat karni hai, main bohot gussa hoon!")
        page.locator(".text-turn button").click()
        print("Sent handoff request turn...")

        page.wait_for_selector(".banner.handoff", timeout=30000)
        bubbles = page.locator(".bubble p").all_inner_texts()
        reply2 = bubbles[-1]
        print(f"Agent handoff reply: {reply2}")
        print("Handoff banner confirmed visible.")

        # Check telemetry strip
        strip_text = page.locator(".strip").inner_text()
        print(f"Telemetry strip: {strip_text}")
        assert "Turn" in strip_text

        # Take screenshot of the complete single page flow
        page.screenshot(path="review/phase_final/browser_talk_verified.png", full_page=True)
        print("Saved screenshot to review/phase_final/browser_talk_verified.png")

        browser.close()
        print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run()
