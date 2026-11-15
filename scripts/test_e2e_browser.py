from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("Navigating to http://127.0.0.1:5174 ...")
        page.goto("http://127.0.0.1:5174", timeout=20000)
        page.wait_for_selector("h1")
        assert "Say it. Hatch it." in page.inner_text("h1")
        print("Page title and hero loaded.")

        # Test Seeded example demo request button
        demo_btn = page.locator("button:has-text('Use demo request')")
        assert demo_btn.is_visible()
        demo_btn.click()
        val = page.locator("textarea").first.input_value()
        assert "ORD-1001" in val
        assert "ORD-1010" in val
        print("Demo request seeded:", val[:60], "...")

        # Click Compile from text
        compile_btn = page.locator("button:has-text('Compile from text')")
        compile_btn.click()
        print("Compiling agent from text...")

        # Wait for spec to appear
        page.wait_for_selector(".spec", timeout=60000)
        spec_title = page.locator("#spec-title").inner_text()
        print(f"Agent compiled successfully: {spec_title}")
        badges = page.locator(".badge").all_inner_texts()
        print(f"Provenance badges: {badges}")
        assert len(badges) >= 4

        # Verify URL updated to /a/<id>
        url = page.url
        print(f"Current page URL: {url}")
        assert "/a/" in url
        agent_id = url.split("/a/")[-1]

        # Test simulated callers (Step 3)
        test_btn = page.locator("button:has-text('simulated callers')")
        assert test_btn.is_visible()
        print("Running 7 simulated callers...")
        test_btn.click()

        # Wait for test report
        page.wait_for_selector(".report", timeout=180000)
        report_title = page.locator("#report-title").inner_text()
        print(f"Test report: {report_title}")
        rows = page.locator("table tbody tr").count()
        print(f"Verdicts table row count: {rows}")
        assert rows == 7

        # Test Step 4: Talk Panel
        talk_section = page.locator("#talk-section")
        assert talk_section.is_visible()
        print("Talk section is visible on single page.")

        # Send text turn: order lookup
        input_box = page.locator(".text-turn input")
        input_box.fill("Mera order ORD-1004 kahan hai?")
        page.locator(".text-turn button").click()
        print("Sent order lookup turn...")

        # Wait for response in chat
        page.wait_for_function("document.querySelectorAll('.bubble').length >= 3", timeout=30000)
        bubbles = page.locator(".bubble p").all_inner_texts()
        reply1 = bubbles[-1]
        print(f"Agent order reply: {reply1}")
        assert "ORD-1004" in reply1 or "delay" in reply1.lower()

        # Send angry turn for human handoff
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

        # Test direct reload / direct URL navigation
        print(f"Testing direct visit to http://127.0.0.1:5174/a/{agent_id} ...")
        page2 = browser.new_page()
        page2.goto(f"http://127.0.0.1:5174/a/{agent_id}", timeout=20000)
        page2.wait_for_selector("#talk-title", timeout=15000)
        assert spec_title in page2.locator("#spec-title").inner_text()
        print("Direct /a/<id> navigation verified!")

        browser.close()
        print("ALL BROWSER E2E TESTS PASSED!")

if __name__ == "__main__":
    run()
