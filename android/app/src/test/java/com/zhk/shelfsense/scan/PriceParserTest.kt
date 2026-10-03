package com.zhk.shelfsense.scan

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PriceParserTest {

    @Test
    fun `parses dollar sign with decimal`() = assertEquals(349, PriceParser.parseCents("$3.49"))

    @Test
    fun `parses price without dollar sign`() = assertEquals(1099, PriceParser.parseCents("10.99 ea"))

    @Test
    fun `parses superscript cents read as run-on digits`() = assertEquals(349, PriceParser.parseCents("$349"))

    @Test
    fun `ignores text without a price`() = assertNull(PriceParser.parseCents("Honey Nut Cereal 10oz"))

    @Test
    fun `picks physically largest price over unit price`() {
        val best = PriceParser.bestPrice(
            listOf(
                PriceCandidate("$0.43 per oz", heightPx = 18, confidence = 0.9f),
                PriceCandidate("$4.59", heightPx = 96, confidence = 0.95f),
                PriceCandidate("Honey Nut Cereal", heightPx = 30, confidence = 0.99f),
            )
        )
        assertEquals(459, best?.cents)
        assertEquals(0.95f, best?.confidence ?: 0f, 0.001f)
    }

    @Test
    fun `returns null when nothing looks like a price`() =
        assertNull(PriceParser.bestPrice(listOf(PriceCandidate("AISLE D4", 40, 0.9f))))
}
