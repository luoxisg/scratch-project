import unittest
from policy import decide


class TestPolicy(unittest.TestCase):
    def test_both_yes(self):
        self.assertEqual(decide("通过", "通过"), "充分且必要（待实际验证）")

    def test_sufficient_not_necessary(self):
        self.assertEqual(decide("通过", "不通过"), "有效但可替代")

    def test_need_but_inadequate(self):
        self.assertEqual(decide("不通过", "通过"), "需求存在但方案不足")

    def test_both_no(self):
        self.assertEqual(decide("不通过", "不通过"), "暂不支持立项")

    def test_unknown_never_promoted_to_pass(self):
        self.assertEqual(decide("证据不足", "通过"), "需要补证")
        self.assertEqual(decide("不通过", "证据不足"), "需要补证")

    def test_invalid(self):
        with self.assertRaises(ValueError):
            decide("大概可以", "通过")


if __name__ == "__main__":
    unittest.main()
